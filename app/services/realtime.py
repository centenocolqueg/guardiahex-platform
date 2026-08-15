from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class RealtimeConnection:
    """
    Representa una conexión WebSocket activa.

    scope:
    - MASTER
    - PARTNER

    El MASTER puede recibir eventos globales.
    El PARTNER únicamente eventos relacionados
    con su socio/bot.
    """

    connection_id: str
    websocket: WebSocket
    scope: str
    socio_id: int | None = None
    bot_id: int | None = None


class RealtimeService:
    """
    Motor WebSocket de GUARDIAHEXBOT PLATFORM.

    Permite actualizar en tiempo real:

    - Panel MASTER.
    - Panel de socios.
    - Estado ON/OFF de bots.
    - Estadísticas.
    - Créditos.
    - Suscripciones.
    - SELLERS.
    - Configuración.
    - Auditoría.
    - Estado de servicios.

    No utiliza polling constante.
    """

    def __init__(self) -> None:
        self._connections: dict[
            str,
            RealtimeConnection,
        ] = {}

        self._lock = asyncio.Lock()

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _normalize_scope(
        scope: str,
    ) -> str:
        value = str(scope).strip().upper()

        if value not in {
            "MASTER",
            "PARTNER",
        }:
            raise ValueError(
                "Scope WebSocket inválido."
            )

        return value

    @staticmethod
    def create_event(
        *,
        event_type: str,
        data: dict[str, Any] | None = None,
        bot_id: int | None = None,
        socio_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Construye el formato estándar de eventos.
        """

        return {
            "event_id": uuid.uuid4().hex,
            "event_type": (
                event_type.strip().upper()
            ),
            "bot_id": bot_id,
            "socio_id": socio_id,
            "data": data or {},
            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

    # =====================================================
    # CONECTAR
    # =====================================================

    async def connect(
        self,
        websocket: WebSocket,
        *,
        scope: str,
        socio_id: int | None = None,
        bot_id: int | None = None,
    ) -> RealtimeConnection:
        """
        Acepta una conexión WebSocket y la registra.
        """

        normalized_scope = (
            self._normalize_scope(scope)
        )

        if (
            normalized_scope == "PARTNER"
            and socio_id is None
        ):
            raise ValueError(
                "Una conexión PARTNER necesita socio_id."
            )

        await websocket.accept()

        connection = RealtimeConnection(
            connection_id=uuid.uuid4().hex,
            websocket=websocket,
            scope=normalized_scope,
            socio_id=socio_id,
            bot_id=bot_id,
        )

        async with self._lock:
            self._connections[
                connection.connection_id
            ] = connection

        await self._safe_send(
            connection,
            self.create_event(
                event_type="CONNECTED",
                data={
                    "connection_id": (
                        connection.connection_id
                    ),
                    "scope": normalized_scope,
                },
                bot_id=bot_id,
                socio_id=socio_id,
            ),
        )

        return connection

    # =====================================================
    # DESCONECTAR
    # =====================================================

    async def disconnect(
        self,
        connection_id: str,
    ) -> None:
        async with self._lock:
            self._connections.pop(
                connection_id,
                None,
            )

    # =====================================================
    # ENVÍO SEGURO
    # =====================================================

    async def _safe_send(
        self,
        connection: RealtimeConnection,
        payload: dict[str, Any],
    ) -> bool:
        """
        Envía JSON sin permitir que una conexión caída
        rompa el broadcast completo.
        """

        try:
            await connection.websocket.send_json(
                payload
            )

            return True

        except Exception:
            await self.disconnect(
                connection.connection_id
            )

            return False

    # =====================================================
    # SNAPSHOT DE CONEXIONES
    # =====================================================

    async def _snapshot(
        self,
    ) -> list[RealtimeConnection]:
        async with self._lock:
            return list(
                self._connections.values()
            )

    # =====================================================
    # EVENTO GLOBAL PARA MASTER
    # =====================================================

    async def publish_master(
        self,
        *,
        event_type: str,
        data: dict[str, Any] | None = None,
        bot_id: int | None = None,
        socio_id: int | None = None,
    ) -> int:
        """
        Envía un evento a todos los paneles MASTER.
        """

        payload = self.create_event(
            event_type=event_type,
            data=data,
            bot_id=bot_id,
            socio_id=socio_id,
        )

        connections = await self._snapshot()

        sent = 0

        for connection in connections:
            if connection.scope != "MASTER":
                continue

            if await self._safe_send(
                connection,
                payload,
            ):
                sent += 1

        return sent

    # =====================================================
    # EVENTO PARA UN SOCIO
    # =====================================================

    async def publish_partner(
        self,
        *,
        socio_id: int,
        event_type: str,
        data: dict[str, Any] | None = None,
        bot_id: int | None = None,
    ) -> int:
        """
        Envía un evento únicamente a las conexiones
        pertenecientes al socio indicado.

        El MASTER también recibe una copia.
        """

        payload = self.create_event(
            event_type=event_type,
            data=data,
            bot_id=bot_id,
            socio_id=socio_id,
        )

        connections = await self._snapshot()

        sent = 0

        for connection in connections:
            allowed = (
                connection.scope == "MASTER"
                or (
                    connection.scope == "PARTNER"
                    and connection.socio_id
                    == socio_id
                )
            )

            if not allowed:
                continue

            if await self._safe_send(
                connection,
                payload,
            ):
                sent += 1

        return sent

    # =====================================================
    # EVENTO PARA UN BOT
    # =====================================================

    async def publish_bot(
        self,
        *,
        bot_id: int,
        event_type: str,
        data: dict[str, Any] | None = None,
        socio_id: int | None = None,
    ) -> int:
        """
        Envía un evento al MASTER y al panel del socio
        relacionado con un bot específico.
        """

        payload = self.create_event(
            event_type=event_type,
            data=data,
            bot_id=bot_id,
            socio_id=socio_id,
        )

        connections = await self._snapshot()

        sent = 0

        for connection in connections:
            if connection.scope == "MASTER":
                allowed = True

            elif connection.scope == "PARTNER":
                allowed = False

                if (
                    socio_id is not None
                    and connection.socio_id
                    == socio_id
                ):
                    allowed = True

                if (
                    connection.bot_id is not None
                    and connection.bot_id
                    == bot_id
                ):
                    allowed = True

            else:
                allowed = False

            if not allowed:
                continue

            if await self._safe_send(
                connection,
                payload,
            ):
                sent += 1

        return sent

    # =====================================================
    # EVENTOS PREDEFINIDOS
    # =====================================================

    async def bot_status_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
        enabled: bool,
        runtime_status: str,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="BOT_STATUS_CHANGED",
            data={
                "enabled": enabled,
                "runtime_status": runtime_status,
            },
        )

    async def bot_version_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
        version: str,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="BOT_VERSION_CHANGED",
            data={
                "version": version.upper(),
            },
        )

    async def credits_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
        telegram_id: int,
        credits: int,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="CREDITS_CHANGED",
            data={
                "telegram_id": telegram_id,
                "credits": credits,
            },
        )

    async def subscription_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
        telegram_id: int,
        plan: str,
        expires_at: str | None,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="SUBSCRIPTION_CHANGED",
            data={
                "telegram_id": telegram_id,
                "plan": plan,
                "expires_at": expires_at,
            },
        )

    async def staff_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="STAFF_CHANGED",
        )

    async def settings_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
        setting: str,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="SETTINGS_CHANGED",
            data={
                "setting": setting,
            },
        )

    async def statistics_changed(
        self,
        *,
        bot_id: int,
        socio_id: int | None,
    ) -> int:
        return await self.publish_bot(
            bot_id=bot_id,
            socio_id=socio_id,
            event_type="STATISTICS_CHANGED",
        )

    # =====================================================
    # PING
    # =====================================================

    async def ping_all(
        self,
    ) -> int:
        """
        Envía un ping a todas las conexiones activas.
        """

        payload = self.create_event(
            event_type="PING",
            data={
                "server_time": self._utc_now(),
            },
        )

        connections = await self._snapshot()

        sent = 0

        for connection in connections:
            if await self._safe_send(
                connection,
                payload,
            ):
                sent += 1

        return sent

    # =====================================================
    # ESTADÍSTICAS DE CONEXIONES
    # =====================================================

    async def connection_statistics(
        self,
    ) -> dict[str, int]:
        connections = await self._snapshot()

        master = sum(
            1
            for connection in connections
            if connection.scope == "MASTER"
        )

        partners = sum(
            1
            for connection in connections
            if connection.scope == "PARTNER"
        )

        return {
            "total": len(connections),
            "master": master,
            "partners": partners,
        }


realtime_service = RealtimeService()
