from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_authenticated,
    require_superadmin,
)
from app.bots.manager import bot_manager
from app.database import get_db
from app.models.bot import BotModel
from app.models.role import RoleModel
from app.models.socio import SocioModel
from app.models.user import UserModel
from app.services.audit import audit_service
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/bots",
    tags=["Bots"],
)


# =========================================================
# SCHEMAS
# =========================================================

BotVersion = Literal[
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
]


class BotCreateRequest(BaseModel):
    socio_id: int | None = None

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


class PartnerSettingsRequest(BaseModel):
    """
    Únicos enlaces que el socio puede cambiar
    desde su panel.
    """

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
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
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
        puede acceder a cualquier bot.

    PARTNER:
        únicamente bots asociados a su socio_id.
    """

    statement = select(
        BotModel
    ).where(
        BotModel.id == bot_id
    )

    if identity.account_type == "PARTNER":
        if identity.socio_id is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
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
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
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
        maintenance=bot.maintenance,

        channel_url=bot.channel_url,
        group_url=bot.group_url,

        history_chat_id=bot.history_chat_id,
        sales_chat_id=bot.sales_chat_id,

        daily_query_limit=(
            bot.daily_query_limit
        ),

        max_founders=bot.max_founders,

        runtime_status=bot_manager.status(
            bot.id
        ),
    )


# =========================================================
# CREAR BOT - SOLO SUPERADMIN
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
    """
    Crea la configuración de un nuevo bot.

    El token privado se configurará mediante
    la capa segura del servidor y no se devuelve
    por esta API.
    """

    if data.is_master:
        existing_master = await session.execute(
            select(BotModel.id).where(
                BotModel.is_master.is_(True)
            )
        )

        if (
            existing_master
            .scalar_one_or_none()
            is not None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Ya existe un bot MASTER."
                ),
            )

    else:
        if data.socio_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Un bot de socio necesita socio_id."
                ),
            )

        socio_result = await session.execute(
            select(SocioModel.id).where(
                SocioModel.id == data.socio_id
            )
        )

        if (
            socio_result.scalar_one_or_none()
            is None
        ):
            raise HTTPException(
                status_code=404,
                detail="Socio no encontrado.",
            )

    username = _normalize_username(
        data.username
    )

    if username:
        duplicate = await session.execute(
            select(BotModel.id).where(
                func.lower(BotModel.username)
                == username
            )
        )

        if duplicate.scalar_one_or_none():
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Ese username de bot ya existe."
                ),
            )

    bot = BotModel(
        socio_id=(
            None
            if data.is_master
            else data.socio_id
        ),
        username=username,
        display_name=(
            data.display_name.strip()
        ),
        administration_name=(
            _clean_optional(
                data.administration_name
            )
        ),
        is_master=data.is_master,
        version=data.version,
        enabled=False,
        maintenance=False,
        daily_query_limit=(
            data.daily_query_limit
        ),
        max_founders=4,
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
            f"Bot creado: {bot.display_name}"
        ),
    )

    await realtime_service.publish_master(
        event_type="BOT_CREATED",
        bot_id=bot.id,
        socio_id=bot.socio_id,
        data={
            "display_name": bot.display_name,
            "version": bot.version,
        },
    )

    return _bot_response(bot)


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

    return _bot_response(bot)


# =========================================================
# EDITAR BOT - SOLO SUPERADMIN
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

    if "username" in fields:
        username = _normalize_username(
            data.username
        )

        if username:
            duplicate = await session.execute(
                select(BotModel.id).where(
                    func.lower(
                        BotModel.username
                    ) == username,
                    BotModel.id != bot.id,
                )
            )

            if duplicate.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
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
        bot.channel_url = _clean_optional(
            data.channel_url
        )

    if "group_url" in fields:
        bot.group_url = _clean_optional(
            data.group_url
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

    if (
        "maintenance" in fields
        and data.maintenance is not None
    ):
        bot.maintenance = data.maintenance

    if "maintenance_message" in fields:
        bot.maintenance_message = (
            _clean_optional(
                data.maintenance_message
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
        event_type="BOT_UPDATED",
    )

    return _bot_response(bot)


# =========================================================
# ON / OFF
# SUPERADMIN O DUEÑO DEL BOT
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

    managed = bot_manager.get(
        bot.id
    )

    try:
        bot.enabled = True
        bot.last_started_at = datetime.now(
            timezone.utc
        )

        await session.commit()

        # Si ya está cargado en memoria,
        # lo arrancamos inmediatamente.
        if managed is not None:
            managed.enabled = True

            runtime_status = (
                bot_manager.status(bot.id)
            )

            if runtime_status != "ONLINE":
                await bot_manager.restart_bot(
                    bot.id
                )

    except Exception:
        await session.rollback()
        raise

    await realtime_service.bot_status_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        enabled=True,
        runtime_status=(
            bot_manager.status(bot.id)
        ),
    )

    return _bot_response(bot)


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

    managed = bot_manager.get(
        bot.id
    )

    try:
        bot.enabled = False
        bot.last_stopped_at = datetime.now(
            timezone.utc
        )

        await session.commit()

        if managed is not None:
            managed.enabled = False

            await bot_manager.stop_bot(
                bot.id
            )

    except Exception:
        await session.rollback()
        raise

    await realtime_service.bot_status_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        enabled=False,
        runtime_status="OFFLINE",
    )

    return _bot_response(bot)


# =========================================================
# PANEL SOCIO:
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
        bot.channel_url = _clean_optional(
            data.channel_url
        )

    if "group_url" in fields:
        bot.group_url = _clean_optional(
            data.group_url
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
        event_type="PARTNER_SETTINGS_CHANGED",
        data={
            "channel_url": bot.channel_url,
            "group_url": bot.group_url,
        },
    )

    return _bot_response(bot)


# =========================================================
# FUNDADORES / COFUNDADORES
# MÁXIMO 4
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

    # Buscar usuario dentro de este bot.
    user_result = await session.execute(
        select(UserModel).where(
            UserModel.bot_id == bot.id,
            UserModel.telegram_id
            == data.telegram_id,
        )
    )

    user = user_result.scalar_one_or_none()

    # Puede añadirse por Telegram ID aunque todavía
    # no haya ejecutado /register.
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
                RoleModel.bot_id == bot.id,
                RoleModel.role.in_(
                    [
                        "FUNDADOR",
                        "COFUNDADOR",
                    ]
                ),
                RoleModel.is_active.is_(True),
                RoleModel.user_id != user.id,
            )
        )

        current_count = int(
            count_result.scalar_one() or 0
        )

        if current_count >= bot.max_founders:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Este bot ya tiene el máximo "
                    "de 4 FUNDADORES/COFUNDADORES."
                ),
            )

    # Solo un rol fundador activo por persona.
    for role in target_roles:
        role.is_active = (
            role.role == data.role
        )

        if role.is_active:
            role.revoked_at = None
        else:
            role.revoked_at = datetime.now(
                timezone.utc
            )

    selected_role = next(
        (
            role
            for role in target_roles
            if role.role == data.role
        ),
        None,
    )

    if selected_role is None:
        selected_role = RoleModel(
            bot_id=bot.id,
            user_id=user.id,
            role=data.role,
            is_active=True,
            assigned_by_telegram_id=(
                identity.socio_id
                if identity.account_type
                == "PARTNER"
                else None
            ),
            assigned_by_role=(
                identity.account_type
            ),
        )

        session.add(selected_role)

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
            UserModel.bot_id == bot.id,
            RoleModel.bot_id == bot.id,
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
            telegram_id=user.telegram_id,
            username=user.username,
            role=role.role,
            active=role.is_active,
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
            RoleModel.bot_id == bot.id,
            UserModel.bot_id == bot.id,
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
            status_code=404,
            detail=(
                "FUNDADOR/COFUNDADOR "
                "no encontrado."
            ),
        )

    now = datetime.now(timezone.utc)

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
