from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from aiogram import Bot
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_authenticated,
    require_superadmin,
)
from app.bots.manager import bot_manager
from app.config import settings
from app.database import get_db
from app.models.bot import BotModel
from app.models.role import RoleModel
from app.models.socio import SocioModel
from app.models.user import UserModel
from app.security import encrypt_bot_token
from app.services.audit import audit_service
from app.services.bot_runtime import bot_runtime_service
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/bots",
    tags=["Bots"],
)


# =========================================================
# VERSIONES
# =========================================================

BotVersion = Literal[
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
]


# =========================================================
# SCHEMAS
# =========================================================

class BotCreateRequest(BaseModel):
    socio_id: int | None = None

    token: str | None = Field(
        default=None,
        min_length=20,
        max_length=256,
        repr=False,
    )

    username: str | None = Field(
        default=None,
        max_length=100,
    )

    display_name: str = Field(
        min_length=2,
        max_length=120,
    )

    administration_name: str | None = Field(
        default=None,
        max_length=120,
    )

    version: BotVersion = "V1"

    is_master: bool = False

    daily_query_limit: int = Field(
        default=1000,
        ge=1,
        le=100000,
    )


class BotUpdateRequest(BaseModel):
    username: str | None = Field(
        default=None,
        max_length=100,
    )

    display_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    administration_name: str | None = Field(
        default=None,
        max_length=120,
    )

    channel_url: str | None = Field(
        default=None,
        max_length=255,
    )

    group_url: str | None = Field(
        default=None,
        max_length=255,
    )

    history_chat_id: int | None = None
    sales_chat_id: int | None = None

    daily_query_limit: int | None = Field(
        default=None,
        ge=1,
        le=100000,
    )

    maintenance: bool | None = None

    maintenance_message: str | None = Field(
        default=None,
        max_length=1000,
    )


class BotTokenRequest(BaseModel):
    token: str = Field(
        min_length=20,
        max_length=256,
        repr=False,
    )


class PartnerSettingsRequest(BaseModel):
    channel_url: str | None = Field(
        default=None,
        max_length=255,
    )

    group_url: str | None = Field(
        default=None,
        max_length=255,
    )


class FounderRequest(BaseModel):
    telegram_id: int

    role: Literal[
        "FUNDADOR",
        "COFUNDADOR",
    ]


class BotResponse(BaseModel):
    id: int
    socio_id: int | None

    telegram_bot_id: int | None
    username: str | None
    display_name: str
    administration_name: str | None

    is_master: bool
    version: str

    enabled: bool
    maintenance: bool

    token_configured: bool

    channel_url: str | None
    group_url: str | None

    history_chat_id: int | None
    sales_chat_id: int | None

    daily_query_limit: int
    max_founders: int

    runtime_status: str


class FounderResponse(BaseModel):
    telegram_id: int
    username: str | None
    role: str
    active: bool


# =========================================================
# UTILIDADES
# =========================================================

def _clean_optional(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    value = value.strip()

    return value or None


def _normalize_username(
    value: str | None,
) -> str | None:

    value = _clean_optional(value)

    if value is None:
        return None

    return value.lstrip("@").lower()


def _token_configured(
    bot: BotModel,
) -> bool:

    if bot.token_configured:
        return True

    if (
        bot.is_master
        and settings.master_bot_token.strip()
    ):
        return True

    return False


async def _validate_telegram_token(
    token: str,
) -> tuple[int, str | None]:
    """
    Valida un token directamente con Telegram.

    El token nunca se registra en logs
    ni se devuelve mediante la API.
    """

    clean_token = token.strip()

    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token está vacío.",
        )

    temporary_bot: Bot | None = None

    try:
        temporary_bot = Bot(
            token=clean_token
        )

        info = await temporary_bot.get_me()

        username = (
            info.username.lower()
            if info.username
            else None
        )

        return (
            info.id,
            username,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El token de Telegram es inválido "
                "o no pudo verificarse."
            ),
        ) from exc

    finally:
        if temporary_bot is not None:
            try:
                await temporary_bot.session.close()
            except Exception:
                pass


async def _ensure_unique_telegram_identity(
    session: AsyncSession,
    *,
    telegram_bot_id: int,
    username: str | None,
    exclude_bot_id: int | None = None,
) -> None:

    conditions = [
        BotModel.telegram_bot_id
        == telegram_bot_id
    ]

    if username:
        conditions.append(
            func.lower(
                BotModel.username
            )
            == username.lower()
        )

    statement = select(
        BotModel.id
    ).where(
        or_(*conditions)
    )

    if exclude_bot_id is not None:
        statement = statement.where(
            BotModel.id != exclude_bot_id
        )

    result = await session.execute(
        statement
    )

    duplicate_id = (
        result.scalar_one_or_none()
    )

    if duplicate_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este bot de Telegram ya está "
                "registrado en la plataforma."
            ),
        )


async def _get_bot(
    session: AsyncSession,
    *,
    bot_id: int,
) -> BotModel:

    result = await session.execute(
        select(BotModel).where(
            BotModel.id == bot_id
        )
    )

    bot = result.scalar_one_or_none()

    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot no encontrado.",
        )

    return bot


async def _get_accessible_bot(
    session: AsyncSession,
    *,
    bot_id: int,
    identity: CurrentIdentity,
) -> BotModel:
    """
    SUPERADMIN:
        cualquier bot.

    PARTNER:
        solamente bots de su socio_id.
    """

    statement = select(
        BotModel
    ).where(
        BotModel.id == bot_id
    )

    if identity.account_type == "PARTNER":

        if identity.socio_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta de socio inválida.",
            )

        statement = statement.where(
            BotModel.socio_id
            == identity.socio_id
        )

    result = await session.execute(
        statement
    )

    bot = result.scalar_one_or_none()

    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Bot no encontrado o sin permiso."
            ),
        )

    return bot


def _bot_response(
    bot: BotModel,
) -> BotResponse:

    return BotResponse(
        id=bot.id,
        socio_id=bot.socio_id,

        telegram_bot_id=bot.telegram_bot_id,
        username=bot.username,
        display_name=bot.display_name,

        administration_name=(
            bot.administration_name
        ),

        is_master=bot.is_master,
        version=bot.version,

        enabled=bot.enabled,

        maintenance=(
            bot.maintenance_mode
        ),

        token_configured=(
            _token_configured(bot)
        ),

        channel_url=bot.channel_url,
        group_url=bot.group_url,

        history_chat_id=bot.history_chat_id,
        sales_chat_id=bot.sales_chat_id,

        daily_query_limit=(
            bot.daily_query_limit
        ),

        max_founders=(
            bot.max_founders
        ),

        runtime_status=(
            bot_manager.status(
                bot.id
            )
        ),
    )


# =========================================================
# CREAR BOT
# SOLO SUPERADMIN
# =========================================================

@router.post(
    "",
    response_model=BotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bot(
    data: BotCreateRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    # -----------------------------------------------------
    # MASTER ÚNICO
    # -----------------------------------------------------

    if data.is_master:

        result = await session.execute(
            select(BotModel.id).where(
                BotModel.is_master.is_(True)
            )
        )

        if (
            result.scalar_one_or_none()
            is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Ya existe un bot MASTER."
                ),
            )

    # -----------------------------------------------------
    # BOT DE SOCIO
    # -----------------------------------------------------

    else:

        if data.socio_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Un bot de socio necesita "
                    "un socio_id."
                ),
            )

        socio_result = await session.execute(
            select(SocioModel.id).where(
                SocioModel.id
                == data.socio_id,
                SocioModel.is_active.is_(True),
            )
        )

        if (
            socio_result.scalar_one_or_none()
            is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Socio no encontrado "
                    "o desactivado."
                ),
            )

    supplied_token = _clean_optional(
        data.token
    )

    # Bot de socio siempre necesita token.
    if (
        not data.is_master
        and supplied_token is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Debes proporcionar el token "
                "de BotFather."
            ),
        )

    # MASTER puede usar MASTER_BOT_TOKEN.
    validation_token = supplied_token

    if (
        data.is_master
        and validation_token is None
    ):
        validation_token = (
            settings.master_bot_token.strip()
            or None
        )

    telegram_bot_id: int | None = None

    username = _normalize_username(
        data.username
    )

    # -----------------------------------------------------
    # VALIDAR CON TELEGRAM
    # -----------------------------------------------------

    if validation_token:

        (
            telegram_bot_id,
            telegram_username,
        ) = await _validate_telegram_token(
            validation_token
        )

        username = (
            telegram_username
            or username
        )

        await _ensure_unique_telegram_identity(
            session,
            telegram_bot_id=telegram_bot_id,
            username=username,
        )

    elif username:

        duplicate = await session.execute(
            select(BotModel.id).where(
                func.lower(
                    BotModel.username
                )
                == username
            )
        )

        if (
            duplicate.scalar_one_or_none()
            is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Ese username ya existe."
                ),
            )

    # -----------------------------------------------------
    # CIFRAR TOKEN
    # -----------------------------------------------------

    token_encrypted: str | None = None

    # Solo almacenamos el token si fue enviado
    # explícitamente por el SUPERADMIN.
    #
    # Si MASTER usa MASTER_BOT_TOKEN desde .env,
    # no duplicamos ese secreto en PostgreSQL.

    if supplied_token:

        try:
            token_encrypted = (
                encrypt_bot_token(
                    supplied_token
                )
            )

        except Exception as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "El cifrado de tokens "
                    "no está configurado."
                ),
            ) from exc

    # -----------------------------------------------------
    # CREAR REGISTRO
    # -----------------------------------------------------

    bot = BotModel(
        socio_id=(
            None
            if data.is_master
            else data.socio_id
        ),

        telegram_bot_id=telegram_bot_id,

        username=username,

        display_name=(
            data.display_name.strip()
        ),

        administration_name=(
            _clean_optional(
                data.administration_name
            )
        ),

        token_encrypted=(
            token_encrypted
        ),

        is_master=data.is_master,

        version=data.version,

        enabled=False,

        maintenance_mode=False,

        daily_query_limit=(
            data.daily_query_limit
        ),

        max_founders=(
            settings.max_founders_per_bot
        ),
    )

    session.add(bot)

    try:
        await session.commit()
        await session.refresh(bot)

    except Exception:
        await session.rollback()
        raise

    await audit_service.success(
        session,
        bot_id=bot.id,
        action="BOT_CREATED",
        category="BOT",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        description=(
            f"Bot creado: "
            f"{bot.display_name}"
        ),
    )

    await realtime_service.publish_master(
        event_type="BOT_CREATED",
        bot_id=bot.id,
        socio_id=bot.socio_id,
        data={
            "display_name": (
                bot.display_name
            ),
            "username": (
                bot.username
            ),
            "version": (
                bot.version
            ),
        },
    )

    return _bot_response(
        bot
    )


# =========================================================
# CONFIGURAR / CAMBIAR TOKEN
# SOLO SUPERADMIN
# =========================================================

@router.put(
    "/{bot_id}/token",
    response_model=BotResponse,
)
async def update_bot_token(
    bot_id: int,
    data: BotTokenRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    bot = await _get_bot(
        session,
        bot_id=bot_id,
    )

    runtime_status = (
        bot_manager.status(
            bot.id
        )
    )

    # Cambio de token únicamente con el bot OFF.
    if (
        bot.enabled
        or runtime_status == "ONLINE"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Apaga el bot antes de "
                "cambiar su token."
            ),
        )

    clean_token = data.token.strip()

    (
        telegram_bot_id,
        telegram_username,
    ) = await _validate_telegram_token(
        clean_token
    )

    await _ensure_unique_telegram_identity(
        session,
        telegram_bot_id=telegram_bot_id,
        username=telegram_username,
        exclude_bot_id=bot.id,
    )

    try:
        encrypted = encrypt_bot_token(
            clean_token
        )

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "El cifrado de tokens "
                "no está configurado."
            ),
        ) from exc

    old_token = bot.token_encrypted
    old_telegram_id = bot.telegram_bot_id
    old_username = bot.username

    try:
        bot.token_encrypted = encrypted
        bot.telegram_bot_id = telegram_bot_id

        if telegram_username:
            bot.username = telegram_username

        await session.commit()
        await session.refresh(bot)

        # Eliminar runtime anterior para que
        # el próximo ON cargue el token nuevo.
        if bot_manager.exists(bot.id):
            await bot_manager.unregister_bot(
                bot.id
            )

    except Exception:
        await session.rollback()

        bot.token_encrypted = old_token
        bot.telegram_bot_id = old_telegram_id
        bot.username = old_username

        raise

    await audit_service.success(
        session,
        bot_id=bot.id,
        action="BOT_TOKEN_UPDATED",
        category="BOT",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        description=(
            "Token Telegram actualizado "
            "de forma segura."
        ),
    )

    await realtime_service.publish_bot(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        event_type="BOT_TOKEN_UPDATED",
    )

    return _bot_response(
        bot
    )


# =========================================================
# LISTAR BOTS
# =========================================================

@router.get(
    "",
    response_model=list[BotResponse],
)
async def list_bots(
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> list[BotResponse]:

    statement = select(
        BotModel
    )

    if identity.account_type == "PARTNER":

        if identity.socio_id is None:
            return []

        statement = statement.where(
            BotModel.socio_id
            == identity.socio_id
        )

    statement = statement.order_by(
        BotModel.id.asc()
    )

    result = await session.execute(
        statement
    )

    bots = list(
        result.scalars().all()
    )

    return [
        _bot_response(bot)
        for bot in bots
    ]


# =========================================================
# VER BOT
# =========================================================

@router.get(
    "/{bot_id}",
    response_model=BotResponse,
)
async def get_bot(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    return _bot_response(
        bot
    )


# =========================================================
# EDITAR BOT
# SOLO SUPERADMIN
# =========================================================

@router.patch(
    "/{bot_id}",
    response_model=BotResponse,
)
async def update_bot(
    bot_id: int,
    data: BotUpdateRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    bot = await _get_bot(
        session,
        bot_id=bot_id,
    )

    fields = data.model_fields_set

    maintenance_changed = (
        "maintenance" in fields
        or "maintenance_message" in fields
    )

    if "username" in fields:

        username = _normalize_username(
            data.username
        )

        if username:

            duplicate = await session.execute(
                select(BotModel.id).where(
                    func.lower(
                        BotModel.username
                    )
                    == username,

                    BotModel.id
                    != bot.id,
                )
            )

            if (
                duplicate.scalar_one_or_none()
                is not None
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_409_CONFLICT
                    ),
                    detail=(
                        "Ese username ya pertenece "
                        "a otro bot."
                    ),
                )

        bot.username = username

    if (
        "display_name" in fields
        and data.display_name is not None
    ):
        bot.display_name = (
            data.display_name.strip()
        )

    if "administration_name" in fields:
        bot.administration_name = (
            _clean_optional(
                data.administration_name
            )
        )

    if "channel_url" in fields:
        bot.channel_url = (
            _clean_optional(
                data.channel_url
            )
        )

    if "group_url" in fields:
        bot.group_url = (
            _clean_optional(
                data.group_url
            )
        )

    if "history_chat_id" in fields:
        bot.history_chat_id = (
            data.history_chat_id
        )

    if "sales_chat_id" in fields:
        bot.sales_chat_id = (
            data.sales_chat_id
        )

    if (
        "daily_query_limit" in fields
        and data.daily_query_limit
        is not None
    ):
        bot.daily_query_limit = (
            data.daily_query_limit
        )

    try:
        await session.commit()
        await session.refresh(bot)

    except Exception:
        await session.rollback()
        raise

    # Mantenimiento requiere reconstruir
    # middleware si el bot estaba ONLINE.
    if maintenance_changed:

        new_maintenance = (
            data.maintenance
            if (
                "maintenance" in fields
                and data.maintenance
                is not None
            )
            else bot.maintenance_mode
        )

        new_message = (
            data.maintenance_message
            if "maintenance_message" in fields
            else bot.maintenance_message
        )

        try:
            bot = (
                await bot_runtime_service
                .set_maintenance(
                    session,
                    bot_id=bot.id,
                    enabled=new_maintenance,
                    message=new_message,
                )
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "La configuración se guardó, "
                    "pero no pudo actualizarse "
                    "el runtime del bot."
                ),
            ) from exc

    await realtime_service.publish_bot(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        event_type="BOT_UPDATED",
    )

    return _bot_response(
        bot
    )


# =========================================================
# ENCENDER BOT
# SUPERADMIN O SOCIO PROPIETARIO
# =========================================================

@router.post(
    "/{bot_id}/enable",
    response_model=BotResponse,
)
async def enable_bot(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    if not _token_configured(bot):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este bot no tiene un token "
                "Telegram configurado."
            ),
        )

    try:
        await bot_runtime_service.start(
            session,
            bot_id=bot.id,
        )

        await session.refresh(
            bot
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "No se pudo iniciar el bot. "
                "Verifica el token y la conexión "
                "con Telegram."
            ),
        ) from exc

    await realtime_service.bot_status_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        enabled=True,
        runtime_status=(
            bot_manager.status(
                bot.id
            )
        ),
    )

    return _bot_response(
        bot
    )


# =========================================================
# APAGAR BOT
# =========================================================

@router.post(
    "/{bot_id}/disable",
    response_model=BotResponse,
)
async def disable_bot(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    try:
        await bot_runtime_service.stop(
            session,
            bot_id=bot.id,
        )

        await session.refresh(
            bot
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo apagar "
                "correctamente el bot."
            ),
        ) from exc

    await realtime_service.bot_status_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        enabled=False,
        runtime_status=(
            bot_manager.status(
                bot.id
            )
        ),
    )

    return _bot_response(
        bot
    )


# =========================================================
# PANEL SOCIO
# SOLO CANAL + GRUPO
# =========================================================

@router.patch(
    "/{bot_id}/partner-settings",
    response_model=BotResponse,
)
async def partner_settings(
    bot_id: int,
    data: PartnerSettingsRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotResponse:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    fields = data.model_fields_set

    if "channel_url" in fields:
        bot.channel_url = (
            _clean_optional(
                data.channel_url
            )
        )

    if "group_url" in fields:
        bot.group_url = (
            _clean_optional(
                data.group_url
            )
        )

    try:
        await session.commit()
        await session.refresh(bot)

    except Exception:
        await session.rollback()
        raise

    await realtime_service.publish_bot(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        event_type=(
            "PARTNER_SETTINGS_CHANGED"
        ),
        data={
            "channel_url": (
                bot.channel_url
            ),
            "group_url": (
                bot.group_url
            ),
        },
    )

    return _bot_response(
        bot
    )


# =========================================================
# FUNDADOR / COFUNDADOR
# =========================================================

@router.post(
    "/{bot_id}/founders",
    response_model=FounderResponse,
)
async def add_founder(
    bot_id: int,
    data: FounderRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> FounderResponse:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    user_result = await session.execute(
        select(UserModel).where(
            UserModel.bot_id == bot.id,
            UserModel.telegram_id
            == data.telegram_id,
        )
    )

    user = (
        user_result.scalar_one_or_none()
    )

    if user is None:

        user = UserModel(
            bot_id=bot.id,
            telegram_id=data.telegram_id,
            credits=0,
            current_plan="FREE",
            is_registered=False,
            welcome_bonus_received=False,
            is_active=True,
        )

        session.add(user)

        await session.flush()

    existing_target = await session.execute(
        select(RoleModel).where(
            RoleModel.bot_id == bot.id,
            RoleModel.user_id == user.id,
            RoleModel.role.in_(
                [
                    "FUNDADOR",
                    "COFUNDADOR",
                ]
            ),
        )
    )

    target_roles = list(
        existing_target.scalars().all()
    )

    already_active = any(
        role.role == data.role
        and role.is_active
        for role in target_roles
    )

    if not already_active:

        count_result = await session.execute(
            select(
                func.count(
                    func.distinct(
                        RoleModel.user_id
                    )
                )
            ).where(
                RoleModel.bot_id
                == bot.id,

                RoleModel.role.in_(
                    [
                        "FUNDADOR",
                        "COFUNDADOR",
                    ]
                ),

                RoleModel.is_active.is_(True),

                RoleModel.user_id
                != user.id,
            )
        )

        current_count = int(
            count_result.scalar_one()
            or 0
        )

        if (
            current_count
            >= bot.max_founders
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Este bot ya alcanzó "
                    "el máximo de FUNDADORES/"
                    "COFUNDADORES."
                ),
            )

    now = datetime.now(
        timezone.utc
    )

    for role in target_roles:

        role.is_active = (
            role.role == data.role
        )

        if role.is_active:
            role.revoked_at = None

        else:
            role.revoked_at = now

    selected_role = next(
        (
            role
            for role in target_roles
            if role.role == data.role
        ),
        None,
    )

    if selected_role is None:

        actor_role = getattr(
            identity,
            "role",
            identity.account_type,
        )

        selected_role = RoleModel(
            bot_id=bot.id,
            user_id=user.id,
            role=data.role,
            is_active=True,

            # Una cuenta web de socio tiene socio_id,
            # no necesariamente Telegram ID.
            assigned_by_telegram_id=None,

            assigned_by_role=(
                actor_role
            ),
        )

        session.add(
            selected_role
        )

    else:
        selected_role.is_active = True
        selected_role.revoked_at = None

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await realtime_service.staff_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
    )

    return FounderResponse(
        telegram_id=user.telegram_id,
        username=user.username,
        role=data.role,
        active=True,
    )


# =========================================================
# LISTAR FUNDADORES
# =========================================================

@router.get(
    "/{bot_id}/founders",
    response_model=list[FounderResponse],
)
async def list_founders(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> list[FounderResponse]:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    result = await session.execute(
        select(
            UserModel,
            RoleModel,
        )
        .join(
            RoleModel,
            RoleModel.user_id
            == UserModel.id,
        )
        .where(
            UserModel.bot_id
            == bot.id,

            RoleModel.bot_id
            == bot.id,

            RoleModel.role.in_(
                [
                    "FUNDADOR",
                    "COFUNDADOR",
                ]
            ),

            RoleModel.is_active.is_(True),
        )
        .order_by(
            RoleModel.created_at.asc()
        )
    )

    rows = result.all()

    return [
        FounderResponse(
            telegram_id=(
                user.telegram_id
            ),
            username=(
                user.username
            ),
            role=(
                role.role
            ),
            active=(
                role.is_active
            ),
        )
        for user, role in rows
    ]


# =========================================================
# ELIMINAR FUNDADOR / COFUNDADOR
# =========================================================

@router.delete(
    "/{bot_id}/founders/{telegram_id}",
)
async def remove_founder(
    bot_id: int,
    telegram_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict:

    bot = await _get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    result = await session.execute(
        select(RoleModel)
        .join(
            UserModel,
            UserModel.id
            == RoleModel.user_id,
        )
        .where(
            RoleModel.bot_id
            == bot.id,

            UserModel.bot_id
            == bot.id,

            UserModel.telegram_id
            == telegram_id,

            RoleModel.role.in_(
                [
                    "FUNDADOR",
                    "COFUNDADOR",
                ]
            ),

            RoleModel.is_active.is_(True),
        )
    )

    roles = list(
        result.scalars().all()
    )

    if not roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "FUNDADOR/COFUNDADOR "
                "no encontrado."
            ),
        )

    now = datetime.now(
        timezone.utc
    )

    for role in roles:
        role.is_active = False
        role.revoked_at = now

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await realtime_service.staff_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
    )

    return {
        "success": True,
        "telegram_id": telegram_id,
        "message": (
            "FUNDADOR/COFUNDADOR eliminado."
        ),
    }
