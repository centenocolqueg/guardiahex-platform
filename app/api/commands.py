from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_superadmin,
)
from app.database import get_db
from app.models.bot import BotModel
from app.models.command import (
    BotCommandModel,
    CommandModel,
)
from app.services.audit import audit_service
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/commands",
    tags=["Comandos"],
)


# =========================================================
# SCHEMAS
# =========================================================

class CommandCreateRequest(BaseModel):
    code: str = Field(
        min_length=2,
        max_length=80,
    )

    category: str = Field(
        min_length=2,
        max_length=60,
    )

    command: str = Field(
        min_length=2,
        max_length=80,
    )

    title: str = Field(
        min_length=2,
        max_length=160,
    )

    description: str | None = None

    level: str = Field(
        default="PROFESIONAL",
        max_length=50,
    )

    price: int = Field(
        default=1,
        ge=0,
        le=100000,
    )

    result_type: str = Field(
        default="TEXT",
        max_length=30,
    )

    result_description: str | None = None

    output_formats: list[str] = []

    provider_key: str | None = Field(
        default=None,
        max_length=120,
    )

    available_versions: list[str] = []

    enabled_global: bool = True

    requires_registration: bool = True

    requires_authorization: bool = True

    charge_on_no_results: bool = True

    sort_order: int = 0


class CommandUpdateRequest(BaseModel):
    category: str | None = Field(
        default=None,
        max_length=60,
    )

    command: str | None = Field(
        default=None,
        max_length=80,
    )

    title: str | None = Field(
        default=None,
        max_length=160,
    )

    description: str | None = None

    level: str | None = Field(
        default=None,
        max_length=50,
    )

    price: int | None = Field(
        default=None,
        ge=0,
        le=100000,
    )

    result_type: str | None = Field(
        default=None,
        max_length=30,
    )

    result_description: str | None = None

    output_formats: list[str] | None = None

    provider_key: str | None = Field(
        default=None,
        max_length=120,
    )

    available_versions: list[str] | None = None

    enabled_global: bool | None = None

    requires_registration: bool | None = None

    requires_authorization: bool | None = None

    charge_on_no_results: bool | None = None

    sort_order: int | None = None


class BotCommandOverrideRequest(BaseModel):
    enabled_override: bool | None = None

    price_override: int | None = Field(
        default=None,
        ge=0,
        le=100000,
    )

    level_override: str | None = Field(
        default=None,
        max_length=50,
    )

    title_override: str | None = Field(
        default=None,
        max_length=160,
    )

    result_description_override: str | None = None


class CommandResponse(BaseModel):
    id: int
    code: str
    category: str
    command: str
    title: str

    description: str | None

    level: str
    price: int

    result_type: str
    result_description: str | None

    output_formats: list[str]

    provider_key: str | None

    available_versions: list[str]

    enabled_global: bool

    requires_registration: bool
    requires_authorization: bool
    charge_on_no_results: bool

    sort_order: int


class BotCommandResponse(BaseModel):
    bot_id: int

    command_id: int
    command: str
    title: str
    category: str

    default_enabled: bool
    effective_enabled: bool

    default_price: int
    effective_price: int

    default_level: str
    effective_level: str

    enabled_override: bool | None
    price_override: int | None
    level_override: str | None
    title_override: str | None

    result_description_override: str | None


# =========================================================
# UTILIDADES
# =========================================================

def normalize_command(
    value: str,
) -> str:
    command = value.strip().lower()

    if not command.startswith("/"):
        command = f"/{command}"

    return command


def normalize_code(
    value: str,
) -> str:
    return (
        value
        .strip()
        .upper()
        .replace(" ", "_")
    )


def normalize_category(
    value: str,
) -> str:
    return (
        value
        .strip()
        .upper()
        .replace(" ", "_")
    )


def normalize_versions(
    versions: list[str],
) -> list[str]:
    allowed = {
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
    }

    result: list[str] = []

    for version in versions:
        value = str(version).strip().upper()

        if value not in allowed:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    f"Versión inválida: {value}"
                ),
            )

        if value not in result:
            result.append(value)

    return result


async def get_command_or_404(
    session: AsyncSession,
    *,
    command_id: int,
) -> CommandModel:
    result = await session.execute(
        select(CommandModel).where(
            CommandModel.id == command_id
        )
    )

    command_model = (
        result.scalar_one_or_none()
    )

    if command_model is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="CMD no encontrado.",
        )

    return command_model


async def get_bot_or_404(
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


def command_response(
    command: CommandModel,
) -> CommandResponse:
    return CommandResponse(
        id=command.id,
        code=command.code,
        category=command.category,
        command=command.command,
        title=command.title,
        description=command.description,
        level=command.level,
        price=command.price,
        result_type=command.result_type,
        result_description=(
            command.result_description
        ),
        output_formats=(
            command.output_formats or []
        ),
        provider_key=command.provider_key,
        available_versions=(
            command.available_versions or []
        ),
        enabled_global=(
            command.enabled_global
        ),
        requires_registration=(
            command.requires_registration
        ),
        requires_authorization=(
            command.requires_authorization
        ),
        charge_on_no_results=(
            command.charge_on_no_results
        ),
        sort_order=command.sort_order,
    )


# =========================================================
# LISTAR CATÁLOGO
# SOLO SUPERADMIN
# =========================================================

@router.get(
    "",
    response_model=list[CommandResponse],
)
async def list_commands(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> list[CommandResponse]:
    result = await session.execute(
        select(CommandModel)
        .order_by(
            CommandModel.category.asc(),
            CommandModel.sort_order.asc(),
            CommandModel.id.asc(),
        )
    )

    commands = list(
        result.scalars().all()
    )

    return [
        command_response(command)
        for command in commands
    ]


# =========================================================
# VER CMD
# =========================================================

@router.get(
    "/{command_id}",
    response_model=CommandResponse,
)
async def get_command(
    command_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CommandResponse:
    command_model = await get_command_or_404(
        session,
        command_id=command_id,
    )

    return command_response(
        command_model
    )


# =========================================================
# CREAR CMD
# =========================================================

@router.post(
    "",
    response_model=CommandResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_command(
    data: CommandCreateRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CommandResponse:
    code = normalize_code(
        data.code
    )

    command_name = normalize_command(
        data.command
    )

    existing = await session.execute(
        select(CommandModel.id).where(
            (
                CommandModel.code == code
            )
            | (
                CommandModel.command
                == command_name
            )
        )
    )

    if (
        existing.scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Ya existe un CMD con ese "
                "código o comando."
            ),
        )

    command_model = CommandModel(
        code=code,
        category=normalize_category(
            data.category
        ),
        command=command_name,
        title=data.title.strip(),
        description=data.description,
        level=data.level.strip().upper(),
        price=data.price,
        result_type=(
            data.result_type
            .strip()
            .upper()
        ),
        result_description=(
            data.result_description
        ),
        output_formats=[
            item.strip().upper()
            for item in data.output_formats
            if item.strip()
        ],
        provider_key=(
            data.provider_key.strip()
            if data.provider_key
            else None
        ),
        available_versions=(
            normalize_versions(
                data.available_versions
            )
        ),
        enabled_global=(
            data.enabled_global
        ),
        requires_registration=(
            data.requires_registration
        ),
        requires_authorization=(
            data.requires_authorization
        ),
        charge_on_no_results=(
            data.charge_on_no_results
        ),
        sort_order=data.sort_order,
    )

    session.add(command_model)

    try:
        await session.commit()
        await session.refresh(
            command_model
        )

    except Exception:
        await session.rollback()
        raise

    await audit_service.success(
        session,
        action="COMMAND_CREATED",
        category="COMMAND",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        command=command_model.command,
        description=(
            f"CMD creado: "
            f"{command_model.title}"
        ),
    )

    await realtime_service.publish_master(
        event_type="COMMAND_CREATED",
        data={
            "command_id": command_model.id,
            "command": command_model.command,
            "category": (
                command_model.category
            ),
        },
    )

    return command_response(
        command_model
    )


# =========================================================
# EDITAR CMD
# =========================================================

@router.patch(
    "/{command_id}",
    response_model=CommandResponse,
)
async def update_command(
    command_id: int,
    data: CommandUpdateRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CommandResponse:
    command_model = await get_command_or_404(
        session,
        command_id=command_id,
    )

    fields = data.model_fields_set

    if (
        "category" in fields
        and data.category is not None
    ):
        command_model.category = (
            normalize_category(
                data.category
            )
        )

    if (
        "command" in fields
        and data.command is not None
    ):
        new_command = normalize_command(
            data.command
        )

        duplicate = await session.execute(
            select(CommandModel.id).where(
                CommandModel.command
                == new_command,
                CommandModel.id
                != command_model.id,
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
                    "Ese comando ya está "
                    "registrado."
                ),
            )

        command_model.command = (
            new_command
        )

    if (
        "title" in fields
        and data.title is not None
    ):
        command_model.title = (
            data.title.strip()
        )

    if "description" in fields:
        command_model.description = (
            data.description
        )

    if (
        "level" in fields
        and data.level is not None
    ):
        command_model.level = (
            data.level.strip().upper()
        )

    if (
        "price" in fields
        and data.price is not None
    ):
        command_model.price = data.price

    if (
        "result_type" in fields
        and data.result_type is not None
    ):
        command_model.result_type = (
            data.result_type
            .strip()
            .upper()
        )

    if "result_description" in fields:
        command_model.result_description = (
            data.result_description
        )

    if (
        "output_formats" in fields
        and data.output_formats is not None
    ):
        command_model.output_formats = [
            item.strip().upper()
            for item in data.output_formats
            if item.strip()
        ]

    if "provider_key" in fields:
        command_model.provider_key = (
            data.provider_key.strip()
            if data.provider_key
            else None
        )

    if (
        "available_versions" in fields
        and data.available_versions
        is not None
    ):
        command_model.available_versions = (
            normalize_versions(
                data.available_versions
            )
        )

    if (
        "enabled_global" in fields
        and data.enabled_global is not None
    ):
        command_model.enabled_global = (
            data.enabled_global
        )

    if (
        "requires_registration" in fields
        and data.requires_registration
        is not None
    ):
        command_model.requires_registration = (
            data.requires_registration
        )

    if (
        "requires_authorization" in fields
        and data.requires_authorization
        is not None
    ):
        command_model.requires_authorization = (
            data.requires_authorization
        )

    if (
        "charge_on_no_results" in fields
        and data.charge_on_no_results
        is not None
    ):
        command_model.charge_on_no_results = (
            data.charge_on_no_results
        )

    if (
        "sort_order" in fields
        and data.sort_order is not None
    ):
        command_model.sort_order = (
            data.sort_order
        )

    try:
        await session.commit()
        await session.refresh(
            command_model
        )

    except Exception:
        await session.rollback()
        raise

    await audit_service.success(
        session,
        action="COMMAND_UPDATED",
        category="COMMAND",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        command=command_model.command,
    )

    await realtime_service.publish_master(
        event_type="COMMAND_UPDATED",
        data={
            "command_id": command_model.id,
            "command": command_model.command,
        },
    )

    return command_response(
        command_model
    )


# =========================================================
# ACTIVAR / DESACTIVAR GLOBALMENTE
# =========================================================

@router.post(
    "/{command_id}/enable",
    response_model=CommandResponse,
)
async def enable_command(
    command_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CommandResponse:
    command_model = await get_command_or_404(
        session,
        command_id=command_id,
    )

    command_model.enabled_global = True

    try:
        await session.commit()
        await session.refresh(
            command_model
        )

    except Exception:
        await session.rollback()
        raise

    await realtime_service.publish_master(
        event_type="COMMAND_STATUS_CHANGED",
        data={
            "command_id": command_model.id,
            "enabled": True,
        },
    )

    return command_response(
        command_model
    )


@router.post(
    "/{command_id}/disable",
    response_model=CommandResponse,
)
async def disable_command(
    command_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CommandResponse:
    command_model = await get_command_or_404(
        session,
        command_id=command_id,
    )

    command_model.enabled_global = False

    try:
        await session.commit()
        await session.refresh(
            command_model
        )

    except Exception:
        await session.rollback()
        raise

    await realtime_service.publish_master(
        event_type="COMMAND_STATUS_CHANGED",
        data={
            "command_id": command_model.id,
            "enabled": False,
        },
    )

    return command_response(
        command_model
    )


# =========================================================
# VER CMD EFECTIVOS DE UN BOT
# =========================================================

@router.get(
    "/bot/{bot_id}",
    response_model=list[BotCommandResponse],
)
async def get_bot_commands(
    bot_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> list[BotCommandResponse]:
    bot = await get_bot_or_404(
        session,
        bot_id=bot_id,
    )

    result = await session.execute(
        select(
            CommandModel,
            BotCommandModel,
        )
        .outerjoin(
            BotCommandModel,
            (
                BotCommandModel.command_id
                == CommandModel.id
            )
            & (
                BotCommandModel.bot_id
                == bot.id
            ),
        )
        .order_by(
            CommandModel.category.asc(),
            CommandModel.sort_order.asc(),
            CommandModel.id.asc(),
        )
    )

    rows = result.all()

    responses: list[
        BotCommandResponse
    ] = []

    for command_model, config in rows:
        versions = (
            command_model.available_versions
            or []
        )

        version_allowed = (
            not versions
            or bot.version.upper()
            in {
                item.upper()
                for item in versions
            }
        )

        default_enabled = bool(
            command_model.enabled_global
            and version_allowed
        )

        if config is not None:
            effective_enabled = (
                config.effective_enabled(
                    default_enabled
                )
            )

            effective_price = (
                config.effective_price(
                    command_model.price
                )
            )

            effective_level = (
                config.level_override
                or command_model.level
            )

        else:
            effective_enabled = (
                default_enabled
            )

            effective_price = (
                command_model.price
            )

            effective_level = (
                command_model.level
            )

        responses.append(
            BotCommandResponse(
                bot_id=bot.id,

                command_id=(
                    command_model.id
                ),

                command=(
                    command_model.command
                ),

                title=(
                    config.title_override
                    if (
                        config
                        and config.title_override
                    )
                    else command_model.title
                ),

                category=(
                    command_model.category
                ),

                default_enabled=(
                    default_enabled
                ),

                effective_enabled=(
                    effective_enabled
                ),

                default_price=(
                    command_model.price
                ),

                effective_price=(
                    effective_price
                ),

                default_level=(
                    command_model.level
                ),

                effective_level=(
                    effective_level
                ),

                enabled_override=(
                    config.enabled_override
                    if config
                    else None
                ),

                price_override=(
                    config.price_override
                    if config
                    else None
                ),

                level_override=(
                    config.level_override
                    if config
                    else None
                ),

                title_override=(
                    config.title_override
                    if config
                    else None
                ),

                result_description_override=(
                    config
                    .result_description_override
                    if config
                    else None
                ),
            )
        )

    return responses


# =========================================================
# CONFIGURACIÓN PARTICULAR POR BOT
# =========================================================

@router.put(
    "/bot/{bot_id}/{command_id}",
    response_model=BotCommandResponse,
)
async def set_bot_command_override(
    bot_id: int,
    command_id: int,
    data: BotCommandOverrideRequest,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotCommandResponse:
    bot = await get_bot_or_404(
        session,
        bot_id=bot_id,
    )

    command_model = await get_command_or_404(
        session,
        command_id=command_id,
    )

    result = await session.execute(
        select(BotCommandModel).where(
            BotCommandModel.bot_id
            == bot.id,
            BotCommandModel.command_id
            == command_model.id,
        )
    )

    config = result.scalar_one_or_none()

    if config is None:
        config = BotCommandModel(
            bot_id=bot.id,
            command_id=command_model.id,
        )

        session.add(config)

    fields = data.model_fields_set

    if "enabled_override" in fields:
        config.enabled_override = (
            data.enabled_override
        )

    if "price_override" in fields:
        config.price_override = (
            data.price_override
        )

    if "level_override" in fields:
        config.level_override = (
            data.level_override.strip().upper()
            if data.level_override
            else None
        )

    if "title_override" in fields:
        config.title_override = (
            data.title_override.strip()
            if data.title_override
            else None
        )

    if (
        "result_description_override"
        in fields
    ):
        config.result_description_override = (
            data.result_description_override
        )

    try:
        await session.commit()
        await session.refresh(config)

    except Exception:
        await session.rollback()
        raise

    await realtime_service.publish_bot(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        event_type="BOT_COMMAND_CHANGED",
        data={
            "command_id": command_model.id,
            "command": command_model.command,
        },
    )

    versions = (
        command_model.available_versions
        or []
    )

    version_allowed = (
        not versions
        or bot.version.upper()
        in {
            item.upper()
            for item in versions
        }
    )

    default_enabled = bool(
        command_model.enabled_global
        and version_allowed
    )

    return BotCommandResponse(
        bot_id=bot.id,

        command_id=command_model.id,

        command=command_model.command,

        title=(
            config.title_override
            or command_model.title
        ),

        category=command_model.category,

        default_enabled=default_enabled,

        effective_enabled=(
            config.effective_enabled(
                default_enabled
            )
        ),

        default_price=(
            command_model.price
        ),

        effective_price=(
            config.effective_price(
                command_model.price
            )
        ),

        default_level=(
            command_model.level
        ),

        effective_level=(
            config.level_override
            or command_model.level
        ),

        enabled_override=(
            config.enabled_override
        ),

        price_override=(
            config.price_override
        ),

        level_override=(
            config.level_override
        ),

        title_override=(
            config.title_override
        ),

        result_description_override=(
            config
            .result_description_override
        ),
    )


# =========================================================
# ELIMINAR OVERRIDE
# =========================================================

@router.delete(
    "/bot/{bot_id}/{command_id}/override",
)
async def delete_bot_command_override(
    bot_id: int,
    command_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict:
    bot = await get_bot_or_404(
        session,
        bot_id=bot_id,
    )

    command_model = await get_command_or_404(
        session,
        command_id=command_id,
    )

    result = await session.execute(
        select(BotCommandModel).where(
            BotCommandModel.bot_id
            == bot.id,
            BotCommandModel.command_id
            == command_model.id,
        )
    )

    config = result.scalar_one_or_none()

    if config is None:
        return {
            "success": True,
            "message": (
                "El CMD ya utiliza "
                "la configuración global."
            ),
        }

    try:
        await session.delete(config)
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await realtime_service.publish_bot(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        event_type="BOT_COMMAND_CHANGED",
        data={
            "command_id": command_model.id,
            "override_removed": True,
        },
    )

    return {
        "success": True,
        "bot_id": bot.id,
        "command_id": command_model.id,
        "message": (
            "Configuración particular eliminada."
        ),
    }
