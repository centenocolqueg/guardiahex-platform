from __future__ import annotations

from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_superadmin,
)
from app.bots.catalog import (
    CATEGORY_META,
    VERSION_CATEGORY_COUNTS,
    VERSION_COMMAND_LIMITS,
    get_enabled_categories,
)
from app.database import get_db
from app.models.bot import BotModel
from app.services.audit import audit_service
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/versions",
    tags=["Versiones"],
)


BotVersion = Literal[
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
]


# =========================================================
# CONFIGURACIÓN OFICIAL DE VERSIONES
# =========================================================

VERSION_CONFIG: dict[str, dict] = {
    "V1": {
        "name": "INICIAL",
        "price_pen": 250,
        "daily_query_limit": 1000,
        "category_count": 10,
        "command_limit": 25,
    },

    "V2": {
        "name": "INICIAL PLUS",
        "price_pen": 400,
        "daily_query_limit": 2000,
        "category_count": 13,
        "command_limit": 40,
    },

    "V3": {
        "name": "AVANZADO",
        "price_pen": 600,
        "daily_query_limit": 5000,
        "category_count": 16,
        "command_limit": 55,
    },

    "V4": {
        "name": "AVANZADO PLUS",
        "price_pen": 1000,
        "daily_query_limit": 9000,
        "category_count": 18,
        "command_limit": 65,
    },

    "V5": {
        "name": "BUSINESS",
        "price_pen": 1200,
        "daily_query_limit": 10000,
        "category_count": 19,
        "command_limit": 72,
    },
}


# =========================================================
# SCHEMAS
# =========================================================

class CategoryInfo(BaseModel):
    code: str
    title: str
    icon: str


class VersionResponse(BaseModel):
    version: BotVersion
    name: str

    price_pen: int
    daily_query_limit: int

    category_count: int
    command_limit: int

    categories: list[CategoryInfo]


class ChangeBotVersionRequest(BaseModel):
    version: BotVersion


class BotVersionResponse(BaseModel):
    bot_id: int
    username: str | None

    previous_version: str
    current_version: str

    daily_query_limit: int

    category_count: int
    command_limit: int

    status: str


# =========================================================
# UTILIDADES
# =========================================================

def normalize_version(
    version: str,
) -> str:
    value = str(version).strip().upper()

    if value not in VERSION_CONFIG:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Versión inválida.",
        )

    return value


def build_version_response(
    version: str,
) -> VersionResponse:
    version = normalize_version(
        version
    )

    config = VERSION_CONFIG[
        version
    ]

    category_codes = (
        get_enabled_categories(
            version
        )
    )

    categories: list[
        CategoryInfo
    ] = []

    for code in category_codes:
        meta = CATEGORY_META.get(
            code,
            {},
        )

        categories.append(
            CategoryInfo(
                code=code,
                title=str(
                    meta.get(
                        "title",
                        code,
                    )
                ),
                icon=str(
                    meta.get(
                        "icon",
                        "",
                    )
                ),
            )
        )

    return VersionResponse(
        version=version,
        name=config["name"],
        price_pen=config["price_pen"],
        daily_query_limit=(
            config[
                "daily_query_limit"
            ]
        ),
        category_count=(
            VERSION_CATEGORY_COUNTS[
                version
            ]
        ),
        command_limit=(
            VERSION_COMMAND_LIMITS[
                version
            ]
        ),
        categories=categories,
    )


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


# =========================================================
# LISTAR VERSIONES
# =========================================================

@router.get(
    "",
    response_model=list[VersionResponse],
)
async def list_versions(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
) -> list[VersionResponse]:
    """
    Devuelve V1-V5 para el panel MASTER.
    """

    return [
        build_version_response(
            version
        )
        for version in (
            "V1",
            "V2",
            "V3",
            "V4",
            "V5",
        )
    ]


# =========================================================
# VER UNA VERSIÓN
# =========================================================

@router.get(
    "/{version}",
    response_model=VersionResponse,
)
async def get_version(
    version: str,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
) -> VersionResponse:
    return build_version_response(
        version
    )


# =========================================================
# CAMBIAR VERSIÓN DE UN BOT
# SOLO SUPERADMIN
# =========================================================

@router.patch(
    "/bot/{bot_id}",
    response_model=BotVersionResponse,
)
async def change_bot_version(
    bot_id: int,
    data: ChangeBotVersionRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BotVersionResponse:
    """
    Cambia un bot entre:

    V1
    V2
    V3
    V4
    V5

    El socio no puede ejecutar esta ruta.
    """

    bot = await get_bot_or_404(
        session,
        bot_id=bot_id,
    )

    new_version = normalize_version(
        data.version
    )

    previous_version = (
        bot.version
    )

    config = VERSION_CONFIG[
        new_version
    ]

    if (
        previous_version
        == new_version
        and bot.daily_query_limit
        == config["daily_query_limit"]
    ):
        return BotVersionResponse(
            bot_id=bot.id,
            username=bot.username,
            previous_version=(
                previous_version
            ),
            current_version=(
                new_version
            ),
            daily_query_limit=(
                bot.daily_query_limit
            ),
            category_count=(
                VERSION_CATEGORY_COUNTS[
                    new_version
                ]
            ),
            command_limit=(
                VERSION_COMMAND_LIMITS[
                    new_version
                ]
            ),
            status="UNCHANGED",
        )

    try:
        bot.version = new_version

        bot.daily_query_limit = (
            config[
                "daily_query_limit"
            ]
        )

        await session.commit()
        await session.refresh(bot)

    except Exception:
        await session.rollback()
        raise

    # =====================================================
    # AUDITORÍA
    # =====================================================

    await audit_service.success(
        session,
        bot_id=bot.id,
        action="BOT_VERSION_CHANGED",
        category="BOT",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        description=(
            f"Versión modificada "
            f"{previous_version} -> "
            f"{new_version}"
        ),
        extra_data={
            "previous_version": (
                previous_version
            ),
            "new_version": (
                new_version
            ),
            "daily_query_limit": (
                bot.daily_query_limit
            ),
        },
    )

    # =====================================================
    # TIEMPO REAL
    # =====================================================

    await realtime_service.bot_version_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        version=new_version,
    )

    return BotVersionResponse(
        bot_id=bot.id,
        username=bot.username,
        previous_version=(
            previous_version
        ),
        current_version=(
            new_version
        ),
        daily_query_limit=(
            bot.daily_query_limit
        ),
        category_count=(
            VERSION_CATEGORY_COUNTS[
                new_version
            ]
        ),
        command_limit=(
            VERSION_COMMAND_LIMITS[
                new_version
            ]
        ),
        status="UPDATED",
    )


# =========================================================
# TABLA RESUMEN
# =========================================================

@router.get(
    "/summary/table",
)
async def versions_table(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
) -> dict:
    """
    Datos compactos para las tarjetas
    del panel MASTER.
    """

    rows = []

    for version in (
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
    ):
        config = VERSION_CONFIG[
            version
        ]

        rows.append(
            {
                "version": version,
                "name": config["name"],
                "price_pen": (
                    config[
                        "price_pen"
                    ]
                ),
                "buttons": (
                    f"{VERSION_CATEGORY_COUNTS[version]}/19"
                ),
                "commands": (
                    f"{VERSION_COMMAND_LIMITS[version]}/72"
                ),
                "daily_query_limit": (
                    config[
                        "daily_query_limit"
                    ]
                ),
            }
        )

    return {
        "versions": rows,
        "total_versions": 5,
    }
