from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_authenticated,
)
from app.database import get_db
from app.models.bot import BotModel
from app.services.bot_runtime import (
    bot_runtime_service,
)
from app.services.statistics import (
    statistics_service,
)


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


# =========================================================
# DASHBOARD PRINCIPAL
# =========================================================

@router.get("/")
async def dashboard_summary(
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
    Devuelve el resumen principal según
    el tipo de cuenta autenticada.

    SUPERADMIN:
        estadísticas globales.

    PARTNER:
        estadísticas únicamente de sus bots.
    """

    # =====================================================
    # SUPERADMIN
    # =====================================================

    if identity.account_type == "SUPERADMIN":
        global_stats = (
            await statistics_service
            .get_global_statistics(
                session
            )
        )

        bots_result = await session.execute(
            select(BotModel).order_by(
                BotModel.id.asc()
            )
        )

        bots = list(
            bots_result.scalars().all()
        )

        bot_statuses: list[
            dict[str, Any]
        ] = []

        for bot in bots:
            runtime = (
                await bot_runtime_service
                .get_status(
                    session,
                    bot_id=bot.id,
                )
            )

            bot_statuses.append(
                runtime
            )

        return {
            "account": {
                "type": "SUPERADMIN",
                "username": identity.username,
                "display_name": (
                    identity.display_name
                ),
            },
            "statistics": global_stats,
            "bots": bot_statuses,
        }

    # =====================================================
    # SOCIO
    # =====================================================

    if identity.socio_id is None:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail="Cuenta de socio inválida.",
        )

    bots_result = await session.execute(
        select(BotModel)
        .where(
            BotModel.socio_id
            == identity.socio_id
        )
        .order_by(
            BotModel.id.asc()
        )
    )

    bots = list(
        bots_result.scalars().all()
    )

    bot_data: list[
        dict[str, Any]
    ] = []

    for bot in bots:
        statistics = (
            await statistics_service
            .get_bot_statistics(
                session,
                bot_id=bot.id,
            )
        )

        runtime = (
            await bot_runtime_service
            .get_status(
                session,
                bot_id=bot.id,
            )
        )

        bot_data.append(
            {
                "bot": runtime,
                "statistics": statistics,
            }
        )

    return {
        "account": {
            "type": "PARTNER",
            "username": identity.username,
            "display_name": (
                identity.display_name
            ),
            "socio_id": (
                identity.socio_id
            ),
        },
        "bots": bot_data,
    }


# =========================================================
# RESUMEN DE UN BOT
# =========================================================

@router.get("/bot/{bot_id}")
async def bot_dashboard(
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
    Devuelve estadísticas y estado de un bot.

    El SUPERADMIN puede consultar cualquier bot.

    Un socio únicamente puede consultar
    bots asociados a su socio_id.
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
                detail="Cuenta inválida.",
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

    statistics = (
        await statistics_service
        .get_bot_statistics(
            session,
            bot_id=bot.id,
        )
    )

    runtime = (
        await bot_runtime_service
        .get_status(
            session,
            bot_id=bot.id,
        )
    )

    return {
        "bot": runtime,
        "statistics": statistics,
    }


# =========================================================
# ESTADO RÁPIDO
# =========================================================

@router.get("/bot/{bot_id}/status")
async def bot_status(
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
    Endpoint ligero usado por la interfaz
    para consultar el estado de un bot.
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
                detail="Cuenta inválida.",
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

    return await bot_runtime_service.get_status(
        session,
        bot_id=bot.id,
    )
