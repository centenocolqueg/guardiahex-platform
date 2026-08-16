from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


@dataclass
class ManagedBot:
    """
    Bot Telegram cargado en memoria.

    El token existe en memoria únicamente
    mientras el proceso necesita operar el bot.
    Nunca debe mostrarse en logs o respuestas.
    """

    bot_id: int

    token: str = field(
        repr=False,
    )

    username: str | None = None
    is_master: bool = False
    enabled: bool = False

    bot: Bot | None = None
    dispatcher: Dispatcher | None = None

    task: asyncio.Task | None = field(
        default=None,
        repr=False,
    )

    last_error: str | None = None


class BotManager:
    """
    Administrador central de GUARDIAHEXBOT
    y todos los bots pertenecientes a socios.

    Responsabilidades:

    - registrar bots;
    - validar el token con Telegram;
    - iniciar polling;
    - detener polling;
    - reiniciar bots;
    - controlar concurrencia;
    - consultar estado;
    - cerrar sesiones correctamente.
    """

    def __init__(self) -> None:
        self._bots: Dict[
            int,
            ManagedBot,
        ] = {}

        self._locks: Dict[
            int,
            asyncio.Lock,
        ] = {}


    # =====================================================
    # CONSULTAS
    # =====================================================

    def exists(
        self,
        bot_id: int,
    ) -> bool:
        return bot_id in self._bots


    def get(
        self,
        bot_id: int,
    ) -> ManagedBot | None:
        return self._bots.get(
            bot_id
        )


    def all(
        self,
    ) -> list[ManagedBot]:
        return list(
            self._bots.values()
        )


    def _get_lock(
        self,
        bot_id: int,
    ) -> asyncio.Lock:

        lock = self._locks.get(
            bot_id
        )

        if lock is None:
            lock = asyncio.Lock()

            self._locks[
                bot_id
            ] = lock

        return lock


    # =====================================================
    # REGISTRAR
    # =====================================================

    async def register_bot(
        self,
        bot_id: int,
        token: str,
        username: str | None = None,
        is_master: bool = False,
        enabled: bool = False,
    ) -> ManagedBot:
        """
        Registra el bot dentro del proceso.

        Todavía no inicia polling.
        """

        token = token.strip()

        if not token:
            raise ValueError(
                "El token del bot "
                "no puede estar vacío."
            )

        if self.exists(
            bot_id
        ):
            raise ValueError(
                f"El bot con ID {bot_id} "
                "ya está registrado."
            )

        # El propio constructor de Aiogram
        # también valida la estructura básica
        # del token.
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

        self._bots[
            bot_id
        ] = managed_bot

        self._get_lock(
            bot_id
        )

        return managed_bot


    # =====================================================
    # CALLBACK DE TAREA
    # =====================================================

    def _polling_finished(
        self,
        bot_id: int,
        task: asyncio.Task,
    ) -> None:
        """
        Registra internamente si polling terminó
        por un error inesperado.

        Nunca escribe el token en logs.
        """

        managed = self.get(
            bot_id
        )

        if managed is None:
            return

        if task.cancelled():
            return

        try:
            error = task.exception()

        except asyncio.CancelledError:
            return

        if error is not None:
            managed.last_error = (
                f"{type(error).__name__}: "
                f"{error}"
            )


    # =====================================================
    # ENCENDER
    # =====================================================

    async def start_bot(
        self,
        bot_id: int,
    ) -> bool:
        """
        Valida el token e inicia polling.

        Si ya está ONLINE, no crea otro polling.
        """

        managed = self.get(
            bot_id
        )

        if managed is None:
            raise ValueError(
                "Bot no registrado."
            )

        if not managed.enabled:
            return False

        if (
            managed.bot is None
            or managed.dispatcher is None
        ):
            raise RuntimeError(
                "Runtime del bot incompleto."
            )

        lock = self._get_lock(
            bot_id
        )

        async with lock:

            # Evitar doble polling.
            if (
                managed.task is not None
                and not managed.task.done()
            ):
                return True

            managed.last_error = None

            # ==========================================
            # VALIDAR TOKEN CONTRA TELEGRAM
            # ==========================================

            try:
                bot_info = await managed.bot.get_me()

            except Exception as exc:
                managed.last_error = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                raise RuntimeError(
                    "Telegram rechazó el token "
                    "o no fue posible conectar "
                    "con Telegram."
                ) from exc

            # Guardamos username obtenido
            # directamente desde Telegram.
            if bot_info.username:
                managed.username = (
                    bot_info.username.lower()
                )

            # ==========================================
            # POLLING
            # ==========================================

            task = asyncio.create_task(
                managed.dispatcher.start_polling(
                    managed.bot,
                    handle_signals=False,

                    # Importante:
                    # dejamos la sesión abierta para
                    # permitir OFF -> ON sin crear
                    # nuevamente el objeto Bot.
                    close_bot_session=False,
                ),
                name=(
                    f"guardiahex-bot-"
                    f"{bot_id}"
                ),
            )

            managed.task = task

            task.add_done_callback(
                lambda completed_task: (
                    self._polling_finished(
                        bot_id,
                        completed_task,
                    )
                )
            )

            # Dar oportunidad a polling de iniciar.
            await asyncio.sleep(0)

            if task.done():

                if task.cancelled():
                    managed.task = None

                    raise RuntimeError(
                        "El polling fue cancelado "
                        "durante el inicio."
                    )

                error = task.exception()

                managed.task = None

                if error is not None:
                    managed.last_error = (
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                    raise RuntimeError(
                        "El bot no pudo iniciar "
                        "el polling."
                    ) from error

                raise RuntimeError(
                    "El polling terminó "
                    "inesperadamente."
                )

            return True


    # =====================================================
    # APAGAR
    # =====================================================

    async def stop_bot(
        self,
        bot_id: int,
    ) -> bool:
        """
        Detiene polling sin destruir
        el bot registrado.

        Esto permite encenderlo otra vez.
        """

        managed = self.get(
            bot_id
        )

        if managed is None:
            raise ValueError(
                "Bot no registrado."
            )

        lock = self._get_lock(
            bot_id
        )

        async with lock:

            task = managed.task

            if (
                task is not None
                and not task.done()
            ):
                task.cancel()

                try:
                    await task

                except asyncio.CancelledError:
                    pass

                except Exception as exc:
                    managed.last_error = (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

            managed.task = None

            # No cerramos aquí bot.session.
            # Se mantiene disponible para
            # volver a encender este bot.

            return True


    # =====================================================
    # REINICIAR
    # =====================================================

    async def restart_bot(
        self,
        bot_id: int,
    ) -> bool:
        """
        Reinicia un bot registrado.
        """

        managed = self.get(
            bot_id
        )

        if managed is None:
            raise ValueError(
                "Bot no registrado."
            )

        await self.stop_bot(
            bot_id
        )

        managed.enabled = True

        return await self.start_bot(
            bot_id
        )


    # =====================================================
    # CAMBIAR ON / OFF
    # =====================================================

    async def set_enabled(
        self,
        bot_id: int,
        enabled: bool,
    ) -> bool:

        managed = self.get(
            bot_id
        )

        if managed is None:
            raise ValueError(
                "Bot no registrado."
            )

        managed.enabled = bool(
            enabled
        )

        if enabled:
            return await self.start_bot(
                bot_id
            )

        return await self.stop_bot(
            bot_id
        )


    # =====================================================
    # ELIMINAR DEL RUNTIME
    # =====================================================

    async def unregister_bot(
        self,
        bot_id: int,
    ) -> bool:
        """
        Apaga, cierra la sesión Telegram
        y elimina el bot de memoria.
        """

        managed = self.get(
            bot_id
        )

        if managed is None:
            return False

        await self.stop_bot(
            bot_id
        )

        if managed.bot is not None:

            try:
                await managed.bot.session.close()

            except Exception:
                pass

        self._bots.pop(
            bot_id,
            None,
        )

        self._locks.pop(
            bot_id,
            None,
        )

        return True


    # =====================================================
    # ESTADO
    # =====================================================

    def status(
        self,
        bot_id: int,
    ) -> str:

        managed = self.get(
            bot_id
        )

        if managed is None:
            return "NOT_REGISTERED"

        if not managed.enabled:
            return "OFFLINE"

        task = managed.task

        if (
            task is not None
            and not task.done()
        ):
            return "ONLINE"

        if managed.last_error:
            return "ERROR"

        return "STOPPED"


    # =====================================================
    # ERROR DEL RUNTIME
    # =====================================================

    def last_error(
        self,
        bot_id: int,
    ) -> str | None:

        managed = self.get(
            bot_id
        )

        if managed is None:
            return None

        return managed.last_error


    # =====================================================
    # APAGAR TODOS
    # =====================================================

    async def shutdown_all(
        self,
    ) -> None:
        """
        Cierra todos los bots y todas
        las sesiones de Telegram.
        """

        bot_ids = list(
            self._bots.keys()
        )

        for bot_id in bot_ids:

            try:
                await self.unregister_bot(
                    bot_id
                )

            except Exception:
                # El cierre de un bot no debe
                # impedir cerrar los demás.
                continue


bot_manager = BotManager()
