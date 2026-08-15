from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import SubscriptionModel
from app.models.user import UserModel


class SubscriptionError(Exception):
    """Error general del sistema de suscripciones."""


class SubscriptionUserNotFoundError(SubscriptionError):
    """El usuario no existe dentro del bot."""


class InvalidSubscriptionDaysError(SubscriptionError):
    """La cantidad de días no es válida."""


class InvalidPlanError(SubscriptionError):
    """El nombre del plan no es válido."""


class SubscriptionService:
    """
    Motor de suscripciones de GUARDIAHEXBOT.

    /sub administra únicamente:
    - plan;
    - días;
    - fecha de vencimiento.

    Los créditos permanecen totalmente separados
    y son administrados por /cred.
    """

    # =====================================================
    # VALIDACIONES
    # =====================================================

    @staticmethod
    def _validate_days(days: int) -> None:
        if not isinstance(days, int):
            raise InvalidSubscriptionDaysError(
                "Los días deben ser un número entero."
            )

        if days <= 0:
            raise InvalidSubscriptionDaysError(
                "Los días deben ser mayores que cero."
            )

        if days > 3650:
            raise InvalidSubscriptionDaysError(
                "La cantidad de días excede el límite permitido."
            )

    @staticmethod
    def _normalize_plan(plan: str) -> str:
        value = str(plan).strip().upper()

        if not value:
            raise InvalidPlanError(
                "Debes indicar un plan."
            )

        if len(value) > 50:
            raise InvalidPlanError(
                "Nombre de plan inválido."
            )

        return value

    # =====================================================
    # BUSCAR USUARIO
    # =====================================================

    async def _get_user_for_update(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
    ) -> UserModel:
        """
        Obtiene y bloquea temporalmente la fila
        del usuario durante la modificación.
        """

        statement = (
            select(UserModel)
            .where(
                UserModel.bot_id == bot_id,
                UserModel.telegram_id == telegram_id,
            )
            .with_for_update()
        )

        result = await session.execute(statement)

        user = result.scalar_one_or_none()

        if user is None:
            raise SubscriptionUserNotFoundError(
                "Usuario no encontrado dentro de este bot."
            )

        return user

    # =====================================================
    # /sub ID DIAS PLAN
    # =====================================================

    async def add_subscription(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        target_telegram_id: int,
        days: int,
        plan: str,
        activated_by_telegram_id: int | None,
        activated_by_role: str | None,
    ) -> SubscriptionModel:
        """
        Añade días a la suscripción.

        Ejemplo:

        /sub 123456789 30 PREMIUM

        Si el usuario aún tiene días:
            añade los nuevos días al vencimiento actual.

        Si ya venció:
            comienza desde el momento actual.
        """

        self._validate_days(days)

        normalized_plan = self._normalize_plan(
            plan
        )

        try:
            user = await self._get_user_for_update(
                session,
                bot_id=bot_id,
                telegram_id=target_telegram_id,
            )

            now = datetime.now(timezone.utc)

            current_expiration = (
                user.plan_expires_at
            )

            # Si existe una suscripción todavía vigente,
            # sumamos los días desde su vencimiento.
            if (
                current_expiration is not None
                and current_expiration > now
            ):
                starts_at = now
                new_expiration = (
                    current_expiration
                    + timedelta(days=days)
                )

            else:
                starts_at = now
                new_expiration = (
                    now
                    + timedelta(days=days)
                )

            # Desactivamos el registro anterior activo
            # para mantener un único estado actual.
            await session.execute(
                update(SubscriptionModel)
                .where(
                    SubscriptionModel.bot_id
                    == bot_id,
                    SubscriptionModel.user_id
                    == user.id,
                    SubscriptionModel.is_active
                    .is_(True),
                )
                .values(
                    is_active=False
                )
            )

            user.current_plan = (
                normalized_plan
            )

            user.plan_expires_at = (
                new_expiration
            )

            subscription = SubscriptionModel(
                bot_id=bot_id,
                user_id=user.id,
                plan_name=normalized_plan,
                days_added=days,
                starts_at=starts_at,
                expires_at=new_expiration,
                activated_by_telegram_id=(
                    activated_by_telegram_id
                ),
                activated_by_role=(
                    activated_by_role.upper()
                    if activated_by_role
                    else None
                ),
                is_active=True,
            )

            session.add(subscription)

            await session.commit()
            await session.refresh(
                subscription
            )

            return subscription

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # CONSULTAR ESTADO
    # =====================================================

    async def get_subscription_status(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
    ) -> dict:
        statement = select(
            UserModel
        ).where(
            UserModel.bot_id == bot_id,
            UserModel.telegram_id == telegram_id,
        )

        result = await session.execute(
            statement
        )

        user = result.scalar_one_or_none()

        if user is None:
            raise SubscriptionUserNotFoundError(
                "Usuario no encontrado."
            )

        now = datetime.now(timezone.utc)

        expires_at = user.plan_expires_at

        active = bool(
            user.current_plan.upper() != "FREE"
            and expires_at is not None
            and expires_at > now
        )

        remaining_days = 0

        if active and expires_at:
            remaining_seconds = (
                expires_at - now
            ).total_seconds()

            remaining_days = max(
                1,
                int(
                    (
                        remaining_seconds
                        + 86399
                    )
                    // 86400
                ),
            )

        return {
            "bot_id": bot_id,
            "telegram_id": telegram_id,
            "plan": user.current_plan,
            "active": active,
            "expires_at": expires_at,
            "remaining_days": remaining_days,
        }

    # =====================================================
    # CANCELAR SUSCRIPCIÓN
    # =====================================================

    async def cancel_subscription(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        target_telegram_id: int,
    ) -> UserModel:
        """
        Cancela el plan por días.

        IMPORTANTE:
        No elimina ni modifica los créditos
        existentes del usuario.
        """

        try:
            user = await self._get_user_for_update(
                session,
                bot_id=bot_id,
                telegram_id=target_telegram_id,
            )

            user.current_plan = "FREE"
            user.plan_expires_at = None

            await session.execute(
                update(SubscriptionModel)
                .where(
                    SubscriptionModel.bot_id
                    == bot_id,
                    SubscriptionModel.user_id
                    == user.id,
                    SubscriptionModel.is_active
                    .is_(True),
                )
                .values(
                    is_active=False
                )
            )

            await session.commit()
            await session.refresh(user)

            return user

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # LIMPIAR PLANES VENCIDOS
    # =====================================================

    async def expire_outdated_subscriptions(
        self,
        session: AsyncSession,
    ) -> int:
        """
        Marca como vencidas las suscripciones cuyo
        tiempo ya terminó.

        Puede ejecutarse periódicamente desde
        una tarea interna.
        """

        now = datetime.now(timezone.utc)

        result = await session.execute(
            select(UserModel).where(
                UserModel.plan_expires_at
                .is_not(None),
                UserModel.plan_expires_at
                <= now,
                UserModel.current_plan
                != "FREE",
            )
        )

        users = list(
            result.scalars().all()
        )

        if not users:
            return 0

        try:
            user_ids: list[int] = []

            for user in users:
                user.current_plan = "FREE"
                user.plan_expires_at = None
                user_ids.append(user.id)

            await session.execute(
                update(SubscriptionModel)
                .where(
                    SubscriptionModel.user_id
                    .in_(user_ids),
                    SubscriptionModel.is_active
                    .is_(True),
                )
                .values(
                    is_active=False
                )
            )

            await session.commit()

            return len(users)

        except Exception:
            await session.rollback()
            raise


subscription_service = SubscriptionService()
