from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.permissions import can_use_sub
from app.models.plan import SubscriptionModel
from app.models.user import UserModel


# =========================================================
# ERRORES
# =========================================================

class SubscriptionError(Exception):
    """Error general del sistema de suscripciones."""


class SubscriptionUserNotFoundError(SubscriptionError):
    """El usuario no existe dentro del bot."""


class InvalidSubscriptionDaysError(SubscriptionError):
    """La cantidad de días no es válida."""


class InvalidPlanError(SubscriptionError):
    """El nombre del plan no es válido."""


class SubscriptionPermissionError(SubscriptionError):
    """El rol no puede administrar suscripciones."""


class SubscriptionAccountDisabledError(SubscriptionError):
    """La cuenta destino no está operativa."""


# =========================================================
# SERVICIO
# =========================================================

class SubscriptionService:
    """
    Motor de suscripciones de GUARDIAHEXBOT.

    /sub administra exclusivamente:

    - nombre del plan;
    - días;
    - vencimiento.

    Los créditos son independientes y nunca
    se reinician, crean o eliminan desde aquí.
    """

    # =====================================================
    # VALIDACIONES
    # =====================================================

    @staticmethod
    def _validate_days(
        days: int,
    ) -> None:

        # bool es subclase de int en Python.
        if (
            not isinstance(days, int)
            or isinstance(days, bool)
        ):
            raise InvalidSubscriptionDaysError(
                "Los días deben ser un número entero."
            )

        if days <= 0:
            raise InvalidSubscriptionDaysError(
                "Los días deben ser mayores que cero."
            )

        # Máximo 10 años por una sola operación.
        if days > 3650:
            raise InvalidSubscriptionDaysError(
                "La cantidad de días excede "
                "el límite permitido."
            )


    @staticmethod
    def _normalize_plan(
        plan: str,
    ) -> str:

        value = (
            str(plan)
            .strip()
            .upper()
        )

        if not value:
            raise InvalidPlanError(
                "Debes indicar un plan."
            )

        if len(value) > 50:
            raise InvalidPlanError(
                "Nombre de plan inválido."
            )

        # FREE representa ausencia de suscripción,
        # por lo que nunca se asigna mediante /sub.
        if value == "FREE":
            raise InvalidPlanError(
                "FREE no es un plan por días."
            )

        return value


    @staticmethod
    def _validate_manager_role(
        role: str | None,
    ) -> str:

        value = (
            str(role or "")
            .strip()
            .upper()
        )

        if not can_use_sub(value):
            raise SubscriptionPermissionError(
                "Tu rol no puede administrar "
                "suscripciones."
            )

        return value


    @staticmethod
    def _validate_account(
        user: UserModel,
    ) -> None:

        if not user.is_registered:
            raise SubscriptionAccountDisabledError(
                "El usuario no está registrado."
            )

        if not user.is_active:
            raise SubscriptionAccountDisabledError(
                "La cuenta del usuario está inactiva."
            )

        if user.is_banned:
            raise SubscriptionAccountDisabledError(
                "La cuenta del usuario está bloqueada."
            )


    # =====================================================
    # BUSCAR USUARIO CON LOCK
    # =====================================================

    async def _get_user_for_update(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
    ) -> UserModel:

        result = await session.execute(
            select(
                UserModel
            )
            .where(
                UserModel.bot_id == bot_id,
                UserModel.telegram_id
                == telegram_id,
            )
            .with_for_update()
        )

        user = (
            result.scalar_one_or_none()
        )

        if user is None:
            raise SubscriptionUserNotFoundError(
                "Usuario no encontrado "
                "dentro de este bot."
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
        Añade días sin eliminar los días restantes.

        Ejemplo:

        /sub 123456789 30 PREMIUM

        Si vence dentro de 10 días:
            nuevo vencimiento = 40 días.

        Si ya venció:
            comienza desde ahora.

        Los créditos del usuario no se modifican.
        """

        self._validate_days(
            days
        )

        normalized_plan = (
            self._normalize_plan(
                plan
            )
        )

        manager_role = (
            self._validate_manager_role(
                activated_by_role
            )
        )

        try:
            user = (
                await self._get_user_for_update(
                    session,
                    bot_id=bot_id,
                    telegram_id=(
                        target_telegram_id
                    ),
                )
            )

            self._validate_account(
                user
            )

            now = datetime.now(
                timezone.utc
            )

            current_expiration = (
                user.plan_expires_at
            )

            # =================================================
            # CONSERVAR DÍAS RESTANTES
            # =================================================

            if (
                current_expiration is not None
                and current_expiration > now
            ):
                base_expiration = (
                    current_expiration
                )

            else:
                base_expiration = now

            new_expiration = (
                base_expiration
                + timedelta(
                    days=days
                )
            )

            # El nuevo plan entra en vigor inmediatamente.
            starts_at = now

            # =================================================
            # DEJAR UN SOLO REGISTRO ACTIVO
            # =================================================

            await session.execute(
                update(
                    SubscriptionModel
                )
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

            # =================================================
            # ACTUALIZAR ESTADO ACTUAL DEL USUARIO
            # =================================================

            user.current_plan = (
                normalized_plan
            )

            user.plan_expires_at = (
                new_expiration
            )

            # OJO:
            # user.credits NO se modifica.

            subscription = (
                SubscriptionModel(
                    bot_id=bot_id,

                    user_id=user.id,

                    plan_name=(
                        normalized_plan
                    ),

                    days_added=days,

                    starts_at=(
                        starts_at
                    ),

                    expires_at=(
                        new_expiration
                    ),

                    activated_by_telegram_id=(
                        activated_by_telegram_id
                    ),

                    activated_by_role=(
                        manager_role
                    ),

                    is_active=True,
                )
            )

            session.add(
                subscription
            )

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

        result = await session.execute(
            select(
                UserModel
            )
            .where(
                UserModel.bot_id == bot_id,
                UserModel.telegram_id
                == telegram_id,
            )
        )

        user = (
            result.scalar_one_or_none()
        )

        if user is None:
            raise SubscriptionUserNotFoundError(
                "Usuario no encontrado."
            )

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            user.plan_expires_at
        )

        active = bool(
            user.is_registered
            and user.is_active
            and not user.is_banned
            and user.current_plan.upper()
            != "FREE"
            and expires_at is not None
            and expires_at > now
        )

        remaining_days = 0

        if (
            active
            and expires_at is not None
        ):
            remaining_seconds = (
                expires_at - now
            ).total_seconds()

            remaining_days = max(
                1,
                ceil(
                    remaining_seconds
                    / 86400
                ),
            )

        return {
            "bot_id": bot_id,

            "telegram_id": (
                telegram_id
            ),

            "plan": (
                user.current_plan
            ),

            "active": active,

            "expires_at": (
                expires_at
            ),

            "remaining_days": (
                remaining_days
            ),

            "credits": (
                user.credits
            ),

            "is_banned": (
                user.is_banned
            ),

            "is_active": (
                user.is_active
            ),
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
        cancelled_by_role: str,
    ) -> UserModel:
        """
        Cancela únicamente el plan por días.

        Los créditos permanecen intactos.
        """

        self._validate_manager_role(
            cancelled_by_role
        )

        try:
            user = (
                await self._get_user_for_update(
                    session,
                    bot_id=bot_id,
                    telegram_id=(
                        target_telegram_id
                    ),
                )
            )

            user.current_plan = "FREE"
            user.plan_expires_at = None

            # OJO:
            # user.credits permanece intacto.

            await session.execute(
                update(
                    SubscriptionModel
                )
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

            await session.refresh(
                user
            )

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
        *,
        bot_id: int | None = None,
    ) -> int:
        """
        Limpieza periódica.

        Usa bloqueo de filas para evitar que una
        renovación simultánea sea sobrescrita por
        el proceso de expiración.
        """

        now = datetime.now(
            timezone.utc
        )

        statement = (
            select(
                UserModel
            )
            .where(
                UserModel.plan_expires_at
                .is_not(None),

                UserModel.plan_expires_at
                <= now,

                UserModel.current_plan
                != "FREE",
            )
        )

        if bot_id is not None:
            statement = (
                statement.where(
                    UserModel.bot_id
                    == bot_id
                )
            )

        statement = (
            statement
            .with_for_update(
                skip_locked=True
            )
        )

        result = await session.execute(
            statement
        )

        users = list(
            result.scalars().all()
        )

        if not users:
            return 0

        try:
            user_ids: list[int] = []

            for user in users:
                # Volvemos a comprobar después
                # de adquirir el bloqueo.
                if (
                    user.plan_expires_at
                    is None
                    or user.plan_expires_at
                    > now
                ):
                    continue

                user.current_plan = "FREE"
                user.plan_expires_at = None

                user_ids.append(
                    user.id
                )

            if not user_ids:
                return 0

            await session.execute(
                update(
                    SubscriptionModel
                )
                .where(
                    SubscriptionModel.user_id
                    .in_(
                        user_ids
                    ),

                    SubscriptionModel.is_active
                    .is_(True),
                )
                .values(
                    is_active=False
                )
            )

            await session.commit()

            return len(
                user_ids
            )

        except Exception:
            await session.rollback()
            raise


subscription_service = (
    SubscriptionService()
)
