from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditModel


class AuditService:
    """
    Servicio central de auditoría de GUARDIAHEXBOT.

    Registra actividad proveniente de:
    - Telegram.
    - Panel MASTER.
    - Panel de socios.
    - Procesos internos.
    - Servicios externos autorizados.

    Los datos sensibles deben registrarse
    enmascarados siempre que sea posible.
    """

    # =====================================================
    # ENMASCARAR DATOS
    # =====================================================

    @staticmethod
    def mask_value(
        value: str | int | None,
        visible_chars: int = 4,
    ) -> str | None:
        """
        Ejemplo:

        12345678 -> ****5678
        """

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        if visible_chars <= 0:
            return "*" * len(text)

        if len(text) <= visible_chars:
            return "*" * len(text)

        return (
            "*" * (len(text) - visible_chars)
            + text[-visible_chars:]
        )

    # =====================================================
    # CREAR REGISTRO
    # =====================================================

    async def log(
        self,
        session: AsyncSession,
        *,
        action: str,
        bot_id: int | None = None,
        request_id: str | None = None,
        source: str = "SYSTEM",
        category: str = "SYSTEM",
        description: str | None = None,
        actor_telegram_id: int | None = None,
        actor_username: str | None = None,
        actor_role: str | None = None,
        target_telegram_id: int | None = None,
        target_type: str | None = None,
        command: str | None = None,
        argument: str | int | None = None,
        success: bool = True,
        status: str = "COMPLETED",
        error_code: str | None = None,
        error_message: str | None = None,
        credits_charged: int = 0,
        duration_ms: int | None = None,
        extra_data: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> AuditModel:
        """
        Crea un evento de auditoría.

        commit=False permite incluir el registro dentro
        de una transacción mayor y hacer commit después.
        """

        audit = AuditModel(
            bot_id=bot_id,
            request_id=request_id,
            source=source.upper(),
            action=action.upper(),
            category=category.upper(),
            description=description,

            actor_telegram_id=actor_telegram_id,
            actor_username=actor_username,
            actor_role=(
                actor_role.upper()
                if actor_role
                else None
            ),

            target_telegram_id=target_telegram_id,
            target_type=(
                target_type.upper()
                if target_type
                else None
            ),

            command=command,
            masked_argument=self.mask_value(
                argument
            ),

            success=success,
            status=status.upper(),

            error_code=error_code,
            error_message=error_message,

            credits_charged=max(
                0,
                int(credits_charged),
            ),

            duration_ms=duration_ms,

            extra_data=extra_data or {},

            ip_address=ip_address,
            user_agent=user_agent,
        )

        session.add(audit)

        if commit:
            try:
                await session.commit()
                await session.refresh(audit)

            except Exception:
                await session.rollback()
                raise

        return audit

    # =====================================================
    # REGISTRAR ÉXITO
    # =====================================================

    async def success(
        self,
        session: AsyncSession,
        *,
        action: str,
        bot_id: int | None = None,
        category: str = "SYSTEM",
        source: str = "SYSTEM",
        actor_telegram_id: int | None = None,
        actor_username: str | None = None,
        actor_role: str | None = None,
        target_telegram_id: int | None = None,
        target_type: str | None = None,
        command: str | None = None,
        argument: str | int | None = None,
        description: str | None = None,
        credits_charged: int = 0,
        request_id: str | None = None,
        duration_ms: int | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> AuditModel:
        return await self.log(
            session,
            action=action,
            bot_id=bot_id,
            category=category,
            source=source,

            actor_telegram_id=actor_telegram_id,
            actor_username=actor_username,
            actor_role=actor_role,

            target_telegram_id=target_telegram_id,
            target_type=target_type,

            command=command,
            argument=argument,
            description=description,

            success=True,
            status="COMPLETED",

            credits_charged=credits_charged,
            request_id=request_id,
            duration_ms=duration_ms,
            extra_data=extra_data,
        )

    # =====================================================
    # REGISTRAR ERROR
    # =====================================================

    async def error(
        self,
        session: AsyncSession,
        *,
        action: str,
        error_message: str,
        bot_id: int | None = None,
        category: str = "SYSTEM",
        source: str = "SYSTEM",
        actor_telegram_id: int | None = None,
        actor_username: str | None = None,
        actor_role: str | None = None,
        command: str | None = None,
        argument: str | int | None = None,
        error_code: str | None = None,
        request_id: str | None = None,
        duration_ms: int | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> AuditModel:
        return await self.log(
            session,
            action=action,
            bot_id=bot_id,
            category=category,
            source=source,

            actor_telegram_id=actor_telegram_id,
            actor_username=actor_username,
            actor_role=actor_role,

            command=command,
            argument=argument,

            success=False,
            status="ERROR",

            error_code=error_code,
            error_message=error_message,

            request_id=request_id,
            duration_ms=duration_ms,
            extra_data=extra_data,
        )

    # =====================================================
    # HISTORIAL POR BOT
    # =====================================================

    async def get_bot_history(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        limit: int = 100,
    ) -> list[AuditModel]:
        limit = max(
            1,
            min(limit, 500),
        )

        statement = (
            select(AuditModel)
            .where(
                AuditModel.bot_id == bot_id
            )
            .order_by(
                AuditModel.created_at.desc()
            )
            .limit(limit)
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    # =====================================================
    # HISTORIAL POR USUARIO
    # =====================================================

    async def get_user_history(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
        limit: int = 100,
    ) -> list[AuditModel]:
        limit = max(
            1,
            min(limit, 500),
        )

        statement = (
            select(AuditModel)
            .where(
                AuditModel.bot_id == bot_id,
                AuditModel.actor_telegram_id
                == telegram_id,
            )
            .order_by(
                AuditModel.created_at.desc()
            )
            .limit(limit)
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    # =====================================================
    # ERRORES RECIENTES
    # =====================================================

    async def get_recent_errors(
        self,
        session: AsyncSession,
        *,
        bot_id: int | None = None,
        limit: int = 50,
    ) -> list[AuditModel]:
        limit = max(
            1,
            min(limit, 500),
        )

        statement = select(
            AuditModel
        ).where(
            AuditModel.success.is_(False)
        )

        if bot_id is not None:
            statement = statement.where(
                AuditModel.bot_id == bot_id
            )

        statement = (
            statement
            .order_by(
                AuditModel.created_at.desc()
            )
            .limit(limit)
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )


audit_service = AuditService()
