from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.bot import BotModel
from app.models.socio import SocioModel
from app.security import decode_access_token
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/realtime",
    tags=["Tiempo real"],
)


# =========================================================
# AUTENTICACIÓN WEBSOCKET
# =========================================================

async def authenticate_websocket(
    websocket: WebSocket,
) -> dict | None:
    """
    Valida el JWT utilizado por una conexión WebSocket.

    El frontend enviará temporalmente:

    ?token=JWT

    Más adelante, cuando terminemos el login web,
    podremos migrarlo a cookie segura HttpOnly.
    """

    token = websocket.query_params.get(
        "token"
    )

    if not token:
        await websocket.close(
            code=1008,
            reason="Autenticación requerida.",
        )
        return None

    payload = decode_access_token(
        token
    )

    if payload is None:
        await websocket.close(
            code=1008,
            reason="Sesión inválida o expirada.",
        )
        return None

    account_type = str(
        payload.get(
            "account_type",
            "",
        )
    ).upper()

    if account_type not in {
        "SUPERADMIN",
        "PARTNER",
    }:
        await websocket.close(
            code=1008,
            reason="Tipo de cuenta inválido.",
        )
        return None

    return payload


# =========================================================
# WEBSOCKET MASTER
# =========================================================

@router.websocket("/ws/master")
async def master_websocket(
    websocket: WebSocket,
) -> None:
    """
    Canal global del panel SUPERADMIN.

    Recibe eventos de:
    - todos los bots;
    - socios;
    - créditos;
    - versiones;
    - comandos;
    - estadísticas;
    - proveedor;
    - auditoría.
    """

    payload = await authenticate_websocket(
        websocket
    )

    if payload is None:
        return

    account_type = str(
        payload.get(
            "account_type",
            "",
        )
    ).upper()

    if account_type != "SUPERADMIN":
        await websocket.close(
            code=1008,
            reason="Permiso SUPERADMIN requerido.",
        )
        return

    if payload.get("sub") != "superadmin":
        await websocket.close(
            code=1008,
            reason="Token MASTER inválido.",
        )
        return

    connection = await realtime_service.connect(
        websocket,
        scope="MASTER",
    )

    try:
        while True:
            message = await websocket.receive_text()

            value = message.strip().upper()

            if value == "PING":
                await websocket.send_json(
                    realtime_service.create_event(
                        event_type="PONG",
                        data={
                            "connection_id": (
                                connection.connection_id
                            )
                        },
                    )
                )

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:
        await realtime_service.disconnect(
            connection.connection_id
        )


# =========================================================
# WEBSOCKET SOCIO / BOT
# =========================================================

@router.websocket(
    "/ws/partner/{bot_id}"
)
async def partner_websocket(
    websocket: WebSocket,
    bot_id: int,
) -> None:
    """
    Canal en tiempo real del panel pequeño
    de cada socio.

    Un socio únicamente puede conectarse
    a bots que pertenezcan a su socio_id.
    """

    payload = await authenticate_websocket(
        websocket
    )

    if payload is None:
        return

    account_type = str(
        payload.get(
            "account_type",
            "",
        )
    ).upper()

    if account_type != "PARTNER":
        await websocket.close(
            code=1008,
            reason="Cuenta de socio requerida.",
        )
        return

    socio_id_raw = payload.get(
        "socio_id"
    )

    try:
        socio_id = int(
            socio_id_raw
        )

    except (
        TypeError,
        ValueError,
    ):
        await websocket.close(
            code=1008,
            reason="Socio inválido.",
        )
        return

    if payload.get("sub") != (
        f"socio:{socio_id}"
    ):
        await websocket.close(
            code=1008,
            reason="Token de socio inválido.",
        )
        return

    # =====================================================
    # COMPROBAR SOCIO + BOT
    # =====================================================

    async with AsyncSessionLocal() as session:
        socio_result = await session.execute(
            select(
                SocioModel
            ).where(
                SocioModel.id == socio_id,
                SocioModel.is_active.is_(True),
            )
        )

        socio = (
            socio_result.scalar_one_or_none()
        )

        if socio is None:
            await websocket.close(
                code=1008,
                reason=(
                    "Cuenta de socio deshabilitada."
                ),
            )
            return

        bot_result = await session.execute(
            select(
                BotModel
            ).where(
                BotModel.id == bot_id,
                BotModel.socio_id == socio_id,
            )
        )

        bot = (
            bot_result.scalar_one_or_none()
        )

        if bot is None:
            await websocket.close(
                code=1008,
                reason=(
                    "Bot no encontrado o sin permiso."
                ),
            )
            return

    # =====================================================
    # CONECTAR SOCIO
    # =====================================================

    connection = await realtime_service.connect(
        websocket,
        scope="PARTNER",
        socio_id=socio_id,
        bot_id=bot_id,
    )

    try:
        while True:
            message = await websocket.receive_text()

            value = message.strip().upper()

            if value == "PING":
                await websocket.send_json(
                    realtime_service.create_event(
                        event_type="PONG",
                        bot_id=bot_id,
                        socio_id=socio_id,
                        data={
                            "connection_id": (
                                connection.connection_id
                            )
                        },
                    )
                )

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:
        await realtime_service.disconnect(
            connection.connection_id
        )


# =========================================================
# WEBSOCKET SOCIO GENERAL
# =========================================================

@router.websocket(
    "/ws/partner"
)
async def partner_general_websocket(
    websocket: WebSocket,
) -> None:
    """
    Canal general del socio.

    Sirve para cambios que afecten a su cuenta
    completa aunque no correspondan a un solo bot.
    """

    payload = await authenticate_websocket(
        websocket
    )

    if payload is None:
        return

    account_type = str(
        payload.get(
            "account_type",
            "",
        )
    ).upper()

    if account_type != "PARTNER":
        await websocket.close(
            code=1008,
            reason="Cuenta de socio requerida.",
        )
        return

    try:
        socio_id = int(
            payload.get("socio_id")
        )

    except (
        TypeError,
        ValueError,
    ):
        await websocket.close(
            code=1008,
            reason="Socio inválido.",
        )
        return

    if payload.get("sub") != (
        f"socio:{socio_id}"
    ):
        await websocket.close(
            code=1008,
            reason="Token inválido.",
        )
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                SocioModel
            ).where(
                SocioModel.id == socio_id,
                SocioModel.is_active.is_(True),
            )
        )

        socio = (
            result.scalar_one_or_none()
        )

        if socio is None:
            await websocket.close(
                code=1008,
                reason=(
                    "Cuenta de socio deshabilitada."
                ),
            )
            return

    connection = await realtime_service.connect(
        websocket,
        scope="PARTNER",
        socio_id=socio_id,
    )

    try:
        while True:
            message = await websocket.receive_text()

            if message.strip().upper() == "PING":
                await websocket.send_json(
                    realtime_service.create_event(
                        event_type="PONG",
                        socio_id=socio_id,
                        data={
                            "connection_id": (
                                connection.connection_id
                            )
                        },
                    )
                )

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:
        await realtime_service.disconnect(
            connection.connection_id
        )
