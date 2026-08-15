from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, User


class BotContextMiddleware(BaseMiddleware):
    """
    Añade información del bot actual a cada evento.

    Esto es importante en GUARDIAHEXBOT porque
    todos los bots de socios comparten el mismo
    motor, pero deben trabajar aislados por bot_id.
    """

    def __init__(
        self,
        internal_bot_id: int,
        version: str = "V1",
        is_master: bool = False,
    ) -> None:
        self.internal_bot_id = internal_bot_id
        self.version = version.upper()
        self.is_master = is_master

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["internal_bot_id"] = self.internal_bot_id
        data["bot_version"] = self.version
        data["is_master_bot"] = self.is_master

        return await handler(event, data)


class RequestContextMiddleware(BaseMiddleware):
    """
    Crea contexto técnico para cada interacción.

    Cada mensaje o botón recibe:
    - request_id único;
    - timestamp;
    - tiempo inicial de procesamiento.

    Será útil para auditoría y diagnóstico.
    """

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["request_id"] = uuid.uuid4().hex
        data["request_timestamp"] = int(time.time())
        data["request_started_at"] = time.monotonic()

        try:
            return await handler(event, data)

        finally:
            started_at = data.get(
                "request_started_at"
            )

            if started_at is not None:
                data["request_duration_ms"] = round(
                    (
                        time.monotonic()
                        - started_at
                    )
                    * 1000,
                    2,
                )


class TelegramIdentityMiddleware(BaseMiddleware):
    """
    Extrae de forma central la identidad básica
    del usuario y del bot que procesa el evento.

    No consulta todavía la base de datos.
    """

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get(
            "event_from_user"
        )

        bot: Bot | None = data.get("bot")

        if user:
            data["telegram_user_id"] = user.id
            data["telegram_username"] = (
                user.username
            )
            data["telegram_full_name"] = (
                user.full_name
            )
        else:
            data["telegram_user_id"] = None
            data["telegram_username"] = None
            data["telegram_full_name"] = None

        if bot:
            data["telegram_bot_id"] = bot.id
        else:
            data["telegram_bot_id"] = None

        return await handler(event, data)


class MaintenanceMiddleware(BaseMiddleware):
    """
    Permite bloquear temporalmente un bot.

    El SUPERADMIN podrá colocar un bot en
    mantenimiento desde el panel maestro.
    """

    def __init__(
        self,
        maintenance: bool = False,
        message: str | None = None,
    ) -> None:
        self.maintenance = maintenance

        self.message = message or (
            "🛠️ <b>MANTENIMIENTO PROGRAMADO</b>\n\n"
            "El sistema se encuentra temporalmente "
            "en mantenimiento.\n\n"
            "Intente nuevamente en unos minutos."
        )

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self.maintenance:
            return await handler(
                event,
                data,
            )

        message = getattr(
            event,
            "message",
            None,
        )

        if message is None and hasattr(
            event,
            "answer",
        ):
            message = event

        if message is not None:
            try:
                await message.answer(
                    self.message
                )
            except Exception:
                pass

        return None


def setup_middlewares(
    *,
    dispatcher,
    internal_bot_id: int,
    version: str = "V1",
    is_master: bool = False,
    maintenance: bool = False,
) -> None:
    """
    Registra todos los middlewares del sistema
    sobre el Dispatcher de un bot.

    Más adelante podremos añadir aquí:
    - comprobación de usuario registrado;
    - estado BAN;
    - permisos por rol;
    - control de créditos;
    - límites diarios;
    - auditoría en PostgreSQL.
    """

    request_context = (
        RequestContextMiddleware()
    )

    identity_context = (
        TelegramIdentityMiddleware()
    )

    bot_context = BotContextMiddleware(
        internal_bot_id=internal_bot_id,
        version=version,
        is_master=is_master,
    )

    maintenance_context = (
        MaintenanceMiddleware(
            maintenance=maintenance
        )
    )

    dispatcher.update.outer_middleware(
        request_context
    )

    dispatcher.update.outer_middleware(
        identity_context
    )

    dispatcher.update.outer_middleware(
        bot_context
    )

    dispatcher.update.outer_middleware(
        maintenance_context
    )
