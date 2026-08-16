from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.manager import ManagedBot, bot_manager
from app.bots.middleware import setup_middlewares
from app.bots.router import attach_root_router
from app.config import settings
from app.models.bot import BotModel
from app.security import decrypt_bot_token


class BotRuntimeError(Exception):
    """Error general del motor de ejecución de bots."""


class BotNotFoundError(BotRuntimeError):
    """El bot no existe en PostgreSQL."""


class BotTokenRequiredError(BotRuntimeError):
    """El bot no tiene un token Telegram configurado."""


class BotRuntimeService:
    """
    Motor que conecta PostgreSQL con Aiogram.

    Los tokens permanecen cifrados en PostgreSQL
    y solamente se descifran temporalmente en memoria.
    """

    # =====================================================
    # OBTENER BOT
    # =====================================================

    async def get_bot(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> BotModel:

        result = await session.execute(
            select(BotModel).where(
                BotModel.id == bot_id
            )
        )

        bot_model = result.scalar_one_or_none()

        if bot_model is None:
            raise BotNotFoundError(
                "El bot no existe."
            )

        return bot_model

    # =====================================================
    # RESOLVER TOKEN PRIVADO
    # =====================================================

    def resolve_token(
        self,
        bot_model: BotModel,
        *,
        token: str | None = None,
    ) -> str:
        """
        Prioridad:

        1. Token entregado internamente.
        2. Token cifrado almacenado en PostgreSQL.
        3. MASTER_BOT_TOKEN para el bot MASTER.
        """

        if token:
            clean_token = token.strip()

            if clean_token:
                return clean_token

        if bot_model.token_encrypted:
            try:
                return decrypt_bot_token(
                    bot_model.token_encrypted
                )

            except Exception as exc:
                raise BotTokenRequiredError(
                    "No se pudo descifrar "
                    "el token del bot."
                ) from exc

        if (
            bot_model.is_master
            and settings.master_bot_token.strip()
        ):
            return settings.master_bot_token.strip()

        raise BotTokenRequiredError(
            "El bot no tiene un token "
            "Telegram configurado."
        )

    # =====================================================
    # REGISTRAR EN MEMORIA
    # =====================================================

    async def register(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        token: str | None = None,
    ) -> ManagedBot:

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        existing = bot_manager.get(
            bot_model.id
        )

        if existing is not None:
            return existing

        resolved_token = self.resolve_token(
            bot_model,
            token=token,
        )

        try:
            managed = await bot_manager.register_bot(
                bot_id=bot_model.id,
                token=resolved_token,
                username=bot_model.username,
                is_master=bot_model.is_master,
                enabled=False,
            )

            if managed.dispatcher is None:
                raise BotRuntimeError(
                    "No se pudo crear el Dispatcher."
                )

            attach_root_router(
                managed.dispatcher
            )

            setup_middlewares(
                dispatcher=managed.dispatcher,
                internal_bot_id=bot_model.id,
                version=bot_model.version,
                is_master=bot_model.is_master,
                maintenance=(
                    bot_model.maintenance_mode
                ),
            )

            return managed

        except Exception:
            if bot_manager.exists(
                bot_model.id
            ):
                try:
                    await bot_manager.unregister_bot(
                        bot_model.id
                    )
                except Exception:
                    pass

            raise

    # =====================================================
    # ENCENDER
    # =====================================================

    async def start(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        token: str | None = None,
    ) -> bool:
        """
        Primero arranca realmente Aiogram.

        PostgreSQL solamente cambia a enabled=True
        después de confirmar el arranque.
        """

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        managed = bot_manager.get(
            bot_model.id
        )

        newly_registered = False

        if managed is None:
            managed = await self.register(
                session,
                bot_id=bot_model.id,
                token=token,
            )

            newly_registered = True

        managed.enabled = True

        try:
            started = await bot_manager.start_bot(
                bot_model.id
            )

            if not started:
                raise BotRuntimeError(
                    "El bot no pudo iniciar."
                )

            # start_bot() ya ejecutó get_me().
            # Guardamos los datos oficiales obtenidos.
            if managed.bot is not None:
                bot_info = await managed.bot.get_me()

                bot_model.telegram_bot_id = (
                    bot_info.id
                )

                if bot_info.username:
                    bot_model.username = (
                        bot_info.username.lower()
                    )

            bot_model.enabled = True

            bot_model.last_started_at = (
                datetime.now(timezone.utc)
            )

            await session.commit()
            await session.refresh(
                bot_model
            )

            return True

        except Exception:
            managed.enabled = False

            try:
                if bot_manager.status(
                    bot_model.id
                ) == "ONLINE":
                    await bot_manager.stop_bot(
                        bot_model.id
                    )

                if newly_registered:
                    await bot_manager.unregister_bot(
                        bot_model.id
                    )

            except Exception:
                pass

            await session.rollback()

            raise

    # =====================================================
    # APAGAR
    # =====================================================

    async def stop(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> bool:

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        managed = bot_manager.get(
            bot_model.id
        )

        try:
            if managed is not None:
                managed.enabled = False

                await bot_manager.stop_bot(
                    bot_model.id
                )

            bot_model.enabled = False

            bot_model.last_stopped_at = (
                datetime.now(timezone.utc)
            )

            await session.commit()
            await session.refresh(
                bot_model
            )

            return True

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # REINICIAR
    # =====================================================

    async def restart(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        token: str | None = None,
    ) -> bool:

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        resolved_token = self.resolve_token(
            bot_model,
            token=token,
        )

        if bot_manager.exists(
            bot_model.id
        ):
            await bot_manager.unregister_bot(
                bot_model.id
            )

        await self.register(
            session,
            bot_id=bot_model.id,
            token=resolved_token,
        )

        return await self.start(
            session,
            bot_id=bot_model.id,
            token=resolved_token,
        )

    # =====================================================
    # ON / OFF
    # =====================================================

    async def set_enabled(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        enabled: bool,
        token: str | None = None,
    ) -> bool:

        if enabled:
            return await self.start(
                session,
                bot_id=bot_id,
                token=token,
            )

        return await self.stop(
            session,
            bot_id=bot_id,
        )

    # =====================================================
    # ESTADO
    # =====================================================

    async def get_status(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> dict:

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        token_configured = (
            bot_model.token_configured
        )

        if (
            bot_model.is_master
            and settings.master_bot_token.strip()
        ):
            token_configured = True

        return {
            "bot_id": bot_model.id,
            "username": bot_model.username,
            "display_name": bot_model.display_name,
            "version": bot_model.version,
            "is_master": bot_model.is_master,
            "database_enabled": bot_model.enabled,
            "maintenance": (
                bot_model.maintenance_mode
            ),
            "token_configured": token_configured,
            "runtime_status": (
                bot_manager.status(
                    bot_model.id
                )
            ),
            "runtime_error": (
                bot_manager.last_error(
                    bot_model.id
                )
            ),
            "last_started_at": (
                bot_model.last_started_at
            ),
            "last_stopped_at": (
                bot_model.last_stopped_at
            ),
        }

    # =====================================================
    # ACTUALIZAR VERSIÓN
    # =====================================================

    async def update_version(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        version: str,
    ) -> BotModel:

        version = version.strip().upper()

        if version not in {
            "V1",
            "V2",
            "V3",
            "V4",
            "V5",
        }:
            raise BotRuntimeError(
                "Versión de bot inválida."
            )

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        was_online = (
            bot_manager.status(
                bot_model.id
            )
            == "ONLINE"
        )

        try:
            bot_model.version = version

            await session.commit()
            await session.refresh(
                bot_model
            )

        except Exception:
            await session.rollback()
            raise

        if bot_manager.exists(
            bot_model.id
        ):
            if was_online:
                await self.restart(
                    session,
                    bot_id=bot_model.id,
                )
            else:
                await bot_manager.unregister_bot(
                    bot_model.id
                )

        return bot_model

    # =====================================================
    # MANTENIMIENTO
    # =====================================================

    async def set_maintenance(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        enabled: bool,
        message: str | None = None,
    ) -> BotModel:

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        was_online = (
            bot_manager.status(
                bot_model.id
            )
            == "ONLINE"
        )

        try:
            bot_model.maintenance_mode = enabled

            if message is not None:
                bot_model.maintenance_message = (
                    message.strip() or None
                )

            await session.commit()
            await session.refresh(
                bot_model
            )

        except Exception:
            await session.rollback()
            raise

        # El middleware recibe maintenance
        # al crear el Dispatcher.
        if bot_manager.exists(
            bot_model.id
        ):
            if was_online:
                await self.restart(
                    session,
                    bot_id=bot_model.id,
                )
            else:
                await bot_manager.unregister_bot(
                    bot_model.id
                )

        return bot_model

    # =====================================================
    # APAGAR TODOS
    # =====================================================

    async def shutdown_all(
        self,
    ) -> None:

        await bot_manager.shutdown_all()


bot_runtime_service = BotRuntimeService()
