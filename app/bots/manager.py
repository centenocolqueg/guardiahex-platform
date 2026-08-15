import asyncio
from dataclasses import dataclass
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.config import settings


@dataclass
class ManagedBot:
    bot_id: int
    token: str
    username: str | None
    is_master: bool
    enabled: bool
    bot: Bot
    dispatcher: Dispatcher
    task: asyncio.Task | None = None


class BotManager:
    """
    Administrador central de GUARDIAHEXBOT y
    todos los bots de socios.

    Permite:
    - Registrar bots.
    - Encender bots.
    - Apagar bots.
    - Reiniciar bots.
    - Consultar estado.
    - Mantener múltiples tokens dentro de
      un solo motor.
    """

    def __init__(self) -> None:
        self._bots: Dict[int, ManagedBot] = {}

    def exists(self, bot_id: int) -> bool:
        return bot_id in self._bots

    def get(self, bot_id: int) -> ManagedBot | None:
        return self._bots.get(bot_id)

    def all(self) -> list[ManagedBot]:
        return list(self._bots.values())

    async def register_bot(
        self,
        bot_id: int,
        token: str,
        username: str | None = None,
        is_master: bool = False,
        enabled: bool = True,
    ) -> ManagedBot:
        """
        Registra un bot dentro del motor central.

        No inicia polling automáticamente.
        """

        if not token:
            raise ValueError("El token del bot no puede estar vacío.")

        if self.exists(bot_id):
            raise ValueError(
                f"El bot con ID {bot_id} ya está registrado."
            )

        bot = Bot(
            token=token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
            ),
        )

        dispatcher = Dispatcher()

        managed_bot = ManagedBot(
            bot_id=bot_id,
            token=token,
            username=username,
            is_master=is_master,
            enabled=enabled,
            bot=bot,
            dispatcher=dispatcher,
        )

        self._bots[bot_id] = managed_bot

        return managed_bot

    async def start_bot(self, bot_id: int) -> bool:
        """
        Enciende un bot registrado.
        """

        managed_bot = self.get(bot_id)

        if not managed_bot:
            raise ValueError("Bot no registrado.")

        if not managed_bot.enabled:
            return False

        if managed_bot.task and not managed_bot.task.done():
            return True

        managed_bot.task = asyncio.create_task(
            managed_bot.dispatcher.start_polling(
                managed_bot.bot,
                handle_signals=False,
            )
        )

        return True

    async def stop_bot(self, bot_id: int) -> bool:
        """
        Apaga un bot sin eliminarlo del sistema.
        """

        managed_bot = self.get(bot_id)

        if not managed_bot:
            raise ValueError("Bot no registrado.")

        if managed_bot.task:
            managed_bot.task.cancel()

            try:
                await managed_bot.task
            except asyncio.CancelledError:
                pass

            managed_bot.task = None

        await managed_bot.bot.session.close()

        return True

    async def restart_bot(self, bot_id: int) -> bool:
        """
        Reinicia un bot.
        """

        await self.stop_bot(bot_id)

        managed_bot = self.get(bot_id)

        if not managed_bot:
            return False

        managed_bot.bot = Bot(
            token=managed_bot.token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
            ),
        )

        return await self.start_bot(bot_id)

    async def set_enabled(
        self,
        bot_id: int,
        enabled: bool,
    ) -> bool:
        """
        Cambia el estado lógico ON/OFF del bot.
        """

        managed_bot = self.get(bot_id)

        if not managed_bot:
            raise ValueError("Bot no registrado.")

        managed_bot.enabled = enabled

        if enabled:
            return await self.start_bot(bot_id)

        return await self.stop_bot(bot_id)

    async def unregister_bot(self, bot_id: int) -> bool:
        """
        Elimina un bot del administrador en memoria.
        """

        managed_bot = self.get(bot_id)

        if not managed_bot:
            return False

        await self.stop_bot(bot_id)

        self._bots.pop(bot_id, None)

        return True

    async def shutdown_all(self) -> None:
        """
        Apaga todos los bots de forma segura.
        """

        bot_ids = list(self._bots.keys())

        for bot_id in bot_ids:
            try:
                await self.stop_bot(bot_id)
            except Exception:
                pass

    def status(self, bot_id: int) -> str:
        managed_bot = self.get(bot_id)

        if not managed_bot:
            return "NOT_REGISTERED"

        if not managed_bot.enabled:
            return "OFFLINE"

        if (
            managed_bot.task is not None
            and not managed_bot.task.done()
        ):
            return "ONLINE"

        return "STOPPED"


bot_manager = BotManager()
