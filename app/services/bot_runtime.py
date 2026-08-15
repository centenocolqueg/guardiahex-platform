from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.manager import ManagedBot, bot_manager
from app.bots.middleware import setup_middlewares
from app.bots.router import attach_root_router
from app.models.bot import BotModel


class BotRuntimeError(Exception):
    """Error general del motor de ejecución de bots."""


class BotNotFoundError(BotRuntimeError):
    """El bot no existe en la base de datos."""


class BotTokenRequiredError(BotRuntimeError):
    """No se proporcionó un token válido para iniciar el bot."""


class BotRuntimeService:
    """
    Conecta la configuración guardada en PostgreSQL
    con el BotManager que mantiene los bots activos
    dentro del servidor.

    Permite:
    - registrar un bot en memoria;
    - encenderlo;
    - apagarlo;
    - reiniciarlo;
    - sincronizar su estado;
    - actualizar fechas de inicio/apagado.

    Cada bot continúa aislado mediante bot_id.
    """

    # =====================================================
    # OBTENER BOT
    # =====================================================

    async def get_bot(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        lock: bool = False,
    ) -> BotModel:
        statement = select(
            BotModel
        ).where(
            BotModel.id == bot_id
        )

        if lock:
            statement = statement.with_for_update()

        result = await session.execute(
            statement
        )

        bot_model = result.scalar_one_or_none()

        if bot_model is None:
            raise BotNotFoundError(
                "El bot no existe."
            )

        return bot_model

    # =====================================================
    # REGISTRAR BOT EN EL MOTOR
    # =====================================================

    async def register(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        token: str,
    ) -> ManagedBot:
        """
        Registra un bot de PostgreSQL dentro
        del motor en memoria.

        El token debe llegar ya resuelto desde
        una fuente privada segura.
        """

        token = token.strip()

        if not token:
            raise BotTokenRequiredError(
                "Se necesita el token privado del bot."
            )

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        existing = bot_manager.get(
            bot_model.id
        )

        if existing is not None:
            return existing

        managed = await bot_manager.register_bot(
            bot_id=bot_model.id,
            token=token,
            username=bot_model.username,
            is_master=bot_model.is_master,
            enabled=bot_model.enabled,
        )

        # Todos los bots usan el mismo motor lógico.
        attach_root_router(
            managed.dispatcher
        )

        # Pero cada uno recibe su propio contexto.
        setup_middlewares(
            dispatcher=managed.dispatcher,
            internal_bot_id=bot_model.id,
            version=bot_model.version,
            is_master=bot_model.is_master,
            maintenance=bot_model.maintenance,
        )

        return managed

    # =====================================================
    # ENCENDER BOT
    # =====================================================

    async def start(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        token: str | None = None,
    ) -> bool:
        """
        Inicia polling para un bot.

        Si todavía no está registrado en memoria,
        será necesario proporcionar su token.
        """

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
            lock=True,
        )

        managed = bot_manager.get(
            bot_model.id
        )

        if managed is None:
            if not token:
                raise BotTokenRequiredError(
                    "El bot todavía no está cargado "
                    "y necesita su token privado."
                )

            managed = await self.register(
                session,
                bot_id=bot_model.id,
                token=token,
            )

        try:
            managed.enabled = True
            bot_model.enabled = True
            bot_model.last_started_at = datetime.now(
                timezone.utc
            )

            await session.commit()

            return await bot_manager.start_bot(
                bot_model.id
            )

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # APAGAR BOT
    # =====================================================

    async def stop(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> bool:
        """
        Apaga un bot y mantiene su configuración
        almacenada en PostgreSQL.
        """

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
            lock=True,
        )

        managed = bot_manager.get(
            bot_model.id
        )

        try:
            bot_model.enabled = False
            bot_model.last_stopped_at = datetime.now(
                timezone.utc
            )

            await session.commit()

            if managed is None:
                return True

            managed.enabled = False

            return await bot_manager.stop_bot(
                bot_model.id
            )

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # REINICIAR BOT
    # =====================================================

    async def restart(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        token: str | None = None,
    ) -> bool:
        """
        Reinicia un bot manteniendo la misma
        configuración.
        """

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
        )

        managed = bot_manager.get(
            bot_model.id
        )

        if managed is None:
            if not token:
                raise BotTokenRequiredError(
                    "Se necesita el token para cargar el bot."
                )

            await self.register(
                session,
                bot_id=bot_model.id,
                token=token,
            )

        try:
            result = await bot_manager.restart_bot(
                bot_model.id
            )

            bot_model.enabled = True
            bot_model.last_started_at = datetime.now(
                timezone.utc
            )

            await session.commit()

            return result

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # CAMBIAR ESTADO ON/OFF
    # =====================================================

    async def set_enabled(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        enabled: bool,
        token: str | None = None,
    ) -> bool:
        """
        Función utilizada por los paneles.

        enabled=True  -> encender
        enabled=False -> apagar
        """

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

        runtime_status = bot_manager.status(
            bot_model.id
        )

        return {
            "bot_id": bot_model.id,
            "username": bot_model.username,
            "display_name": bot_model.display_name,
            "version": bot_model.version,
            "is_master": bot_model.is_master,
            "database_enabled": bot_model.enabled,
            "maintenance": bot_model.maintenance,
            "runtime_status": runtime_status,
            "last_started_at": bot_model.last_started_at,
            "last_stopped_at": bot_model.last_stopped_at,
        }

    # =====================================================
    # ACTUALIZAR VERSIÓN EN RUNTIME
    # =====================================================

    async def update_version(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        version: str,
    ) -> BotModel:
        """
        Guarda la nueva versión.

        V1, V2, V3, V4 o V5.

        El SUPERADMIN será quien tenga permiso
        para ejecutar esta operación.
        """

        version = version.strip().upper()

        allowed = {
            "V1",
            "V2",
            "V3",
            "V4",
            "V5",
        }

        if version not in allowed:
            raise BotRuntimeError(
                "Versión de bot inválida."
            )

        bot_model = await self.get_bot(
            session,
            bot_id=bot_id,
            lock=True,
        )

        try:
            bot_model.version = version

            await session.commit()
            await session.refresh(
                bot_model
            )

            return bot_model

        except Exception:
            await session.rollback()
            raise

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
            lock=True,
        )

        try:
            bot_model.maintenance = enabled

            if message is not None:
                bot_model.maintenance_message = (
                    message.strip()
                    or None
                )

            await session.commit()
            await session.refresh(
                bot_model
            )

            return bot_model

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # APAGAR TODO
    # =====================================================

    async def shutdown_all(self) -> None:
        """
        Se utilizará al apagar FastAPI/systemd
        para cerrar correctamente todos los bots.
        """

        await bot_manager.shutdown_all()


bot_runtime_service = BotRuntimeService()
