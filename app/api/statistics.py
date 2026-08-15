from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_authenticated,
    require_superadmin,
)
from app.database import get_db
from app.models.bot import BotModel
from app.services.statistics import statistics_service


router = APIRouter(
    prefix="/statistics",
    tags=["Estadísticas"],
)


# =========================================================
# UTILIDADES
# =========================================================

async def get_accessible_bot(
    session: AsyncSession,
    *,
    bot_id: int,
    identity: CurrentIdentity,
) -> BotModel:
    """
    SUPERADMIN:
        puede consultar cualquier bot.

    PARTNER:
        solamente bots asociados a su socio_id.
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


# =========================================================
# ESTADÍSTICAS GLOBALES
# SOLO SUPERADMIN
# =========================================================

@router.get("/global")
async def global_statistics(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict[str, Any]:
    """
    Métricas generales de toda la plataforma.

    Incluye:
    - bots;
    - usuarios;
    - SELLERS;
    - créditos;
    - suscripciones;
    - errores.
    """

    return await statistics_service.get_global_statistics(
        session
    )


# =========================================================
# ESTADÍSTICAS COMPLETAS DE UN BOT
# =========================================================

@router.get("/bot/{bot_id}")
async def bot_statistics(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict[str, Any]:
    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    return await statistics_service.get_bot_statistics(
        session,
        bot_id=bot.id,
    )


# =========================================================
# CONSULTAS POR PERIODO
# =========================================================

@router.get("/bot/{bot_id}/queries")
async def query_statistics(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    days: int = Query(
        default=30,
        ge=1,
        le=365,
    ),
) -> dict[str, Any]:
    """
    Estadísticas de consultas de los últimos
    N días.
    """

    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    stats = await statistics_service.query_statistics(
        session,
        bot_id=bot.id,
        days=days,
    )

    return {
        "bot_id": bot.id,
        "period_days": days,
        **stats,
    }


# =========================================================
# MOVIMIENTOS DE CRÉDITOS
# =========================================================

@router.get("/bot/{bot_id}/credits")
async def credit_statistics(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    days: int = Query(
        default=30,
        ge=1,
        le=365,
    ),
) -> dict[str, Any]:
    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    circulating = (
        await statistics_service.total_user_credits(
            session,
            bot_id=bot.id,
        )
    )

    movements = (
        await statistics_service.transaction_statistics(
            session,
            bot_id=bot.id,
            days=days,
        )
    )

    return {
        "bot_id": bot.id,
        "period_days": days,
        "credits_circulating": circulating,
        **movements,
    }


# =========================================================
# SUSCRIPCIONES
# =========================================================

@router.get("/bot/{bot_id}/subscriptions")
async def subscription_statistics(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict[str, Any]:
    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    stats = (
        await statistics_service
        .subscription_statistics(
            session,
            bot_id=bot.id,
        )
    )

    return {
        "bot_id": bot.id,
        **stats,
    }


# =========================================================
# USUARIOS
# =========================================================

@router.get("/bot/{bot_id}/users")
async def user_statistics(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict[str, Any]:
    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    total = await statistics_service.count_users(
        session,
        bot_id=bot.id,
    )

    active = await statistics_service.count_active_users(
        session,
        bot_id=bot.id,
    )

    banned = await statistics_service.count_banned_users(
        session,
        bot_id=bot.id,
    )

    sellers = await statistics_service.count_sellers(
        session,
        bot_id=bot.id,
    )

    return {
        "bot_id": bot.id,
        "total": total,
        "active": active,
        "banned": banned,
        "sellers": sellers,
    }


# =========================================================
# ERRORES
# =========================================================

@router.get("/bot/{bot_id}/errors")
async def error_statistics(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    days: int = Query(
        default=1,
        ge=1,
        le=365,
    ),
) -> dict[str, Any]:
    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    errors = (
        await statistics_service.count_recent_errors(
            session,
            bot_id=bot.id,
            days=days,
        )
    )

    return {
        "bot_id": bot.id,
        "period_days": days,
        "errors": errors,
    }


# =========================================================
# RESUMEN RÁPIDO PARA TARJETAS DEL PANEL
# =========================================================

@router.get("/bot/{bot_id}/cards")
async def dashboard_cards(
    bot_id: int,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_authenticated),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict[str, Any]:
    """
    Datos compactos para las tarjetas visuales
    del dashboard.
    """

    bot = await get_accessible_bot(
        session,
        bot_id=bot_id,
        identity=identity,
    )

    total_users = (
        await statistics_service.count_users(
            session,
            bot_id=bot.id,
        )
    )

    sellers = (
        await statistics_service.count_sellers(
            session,
            bot_id=bot.id,
        )
    )

    credits = (
        await statistics_service.total_user_credits(
            session,
            bot_id=bot.id,
        )
    )

    queries = (
        await statistics_service.query_statistics(
            session,
            bot_id=bot.id,
            days=1,
        )
    )

    subscriptions = (
        await statistics_service
        .subscription_statistics(
            session,
            bot_id=bot.id,
        )
    )

    return {
        "bot_id": bot.id,

        "cards": {
            "users": total_users,
            "queries_today": (
                queries["total"]
            ),
            "credits": credits,
            "active_subscriptions": (
                subscriptions["active"]
            ),
            "sellers": sellers,
            "errors_today": (
                queries["errors"]
            ),
        },
    }
