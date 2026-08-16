from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import RoleModel
from app.models.transaction import TransactionModel
from app.models.user import UserModel


# =========================================================
# ERRORES
# =========================================================

class CreditError(Exception):
    """Error general del sistema de créditos."""


class UserNotFoundError(CreditError):
    """El usuario no existe dentro del bot."""


class InsufficientCreditsError(CreditError):
    """El usuario no tiene créditos suficientes."""


class InvalidCreditAmountError(CreditError):
    """La cantidad de créditos no es válida."""


class CrossBotTransferError(CreditError):
    """Intento de mover saldo entre bots distintos."""


class UnauthorizedCreditOperationError(CreditError):
    """El rol no puede realizar esta operación."""


# =========================================================
# SERVICIO
# =========================================================

class CreditService:
    """
    Motor central de créditos.

    Reglas críticas:

    - Todo saldo está aislado por bot_id.
    - Nunca se permite saldo negativo.
    - SELLER no puede crear créditos.
    - SELLER no puede quitar créditos.
    - SELLER solo transfiere desde su propio saldo.
    - Cada movimiento genera una transacción.
    """

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _validate_amount(
        amount: int,
    ) -> None:

        # bool es subclase de int en Python,
        # por eso lo rechazamos expresamente.
        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
        ):
            raise InvalidCreditAmountError(
                "La cantidad debe ser "
                "un número entero."
            )

        if amount <= 0:
            raise InvalidCreditAmountError(
                "La cantidad debe ser "
                "mayor que cero."
            )


    @staticmethod
    def _normalize_role(
        role: str | None,
    ) -> str:

        if not role:
            return ""

        return (
            str(role)
            .strip()
            .upper()
        )


    @staticmethod
    def _new_reference() -> str:

        return (
            "CR-"
            f"{uuid.uuid4().hex.upper()}"
        )


    # =====================================================
    # BLOQUEO DE USUARIO
    # =====================================================

    async def _get_user_for_update(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
    ) -> UserModel:

        result = await session.execute(
            select(
                UserModel
            )
            .where(
                UserModel.id == user_id,
                UserModel.bot_id == bot_id,
            )
            .with_for_update()
        )

        user = (
            result.scalar_one_or_none()
        )

        if user is None:
            raise UserNotFoundError(
                "Usuario no encontrado "
                "dentro de este bot."
            )

        return user


    # =====================================================
    # PROTECCIÓN SELLER
    # =====================================================

    async def _validate_seller_transfer(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        source: UserModel,
        performed_by_telegram_id: int | None,
        performed_by_role: str | None,
    ) -> None:
        """
        Si el actor es SELLER:

        - debe tener Telegram ID;
        - el saldo origen debe ser suyo;
        - debe poseer rol SELLER activo en ese bot.
        """

        role = self._normalize_role(
            performed_by_role
        )

        if role != "SELLER":
            return

        if performed_by_telegram_id is None:
            raise UnauthorizedCreditOperationError(
                "SELLER requiere identidad Telegram."
            )

        if (
            source.telegram_id
            != performed_by_telegram_id
        ):
            raise UnauthorizedCreditOperationError(
                "SELLER solo puede transferir "
                "desde su propio saldo."
            )

        result = await session.execute(
            select(
                RoleModel.id
            ).where(
                RoleModel.bot_id == bot_id,
                RoleModel.user_id == source.id,
                RoleModel.role == "SELLER",
                RoleModel.is_active.is_(True),
            )
        )

        seller_role = (
            result.scalar_one_or_none()
        )

        if seller_role is None:
            raise UnauthorizedCreditOperationError(
                "El usuario no posee un rol "
                "SELLER activo."
            )


    # =====================================================
    # CONSULTAR SALDO
    # =====================================================

    async def get_balance(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
    ) -> int:

        result = await session.execute(
            select(
                UserModel.credits
            ).where(
                UserModel.id == user_id,
                UserModel.bot_id == bot_id,
            )
        )

        balance = (
            result.scalar_one_or_none()
        )

        if balance is None:
            raise UserNotFoundError(
                "Usuario no encontrado."
            )

        return int(balance)


    # =====================================================
    # AÑADIR CRÉDITOS
    # =====================================================

    async def add_credits(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        target_user_id: int,
        amount: int,
        performed_by_telegram_id: int | None,
        performed_by_role: str | None,
        transaction_type: str = "CREDIT_ADD",
        description: str | None = None,
    ) -> TransactionModel:
        """
        Crea/asigna créditos.

        SELLER queda bloqueado incluso si otra
        capa del sistema olvidó comprobar permisos.
        """

        self._validate_amount(
            amount
        )

        actor_role = self._normalize_role(
            performed_by_role
        )

        if actor_role == "SELLER":
            raise UnauthorizedCreditOperationError(
                "SELLER no puede crear créditos. "
                "Solo puede transferir su saldo."
            )

        try:
            target = (
                await self._get_user_for_update(
                    session,
                    bot_id=bot_id,
                    user_id=target_user_id,
                )
            )

            previous_balance = int(
                target.credits
            )

            target.credits = (
                previous_balance
                + amount
            )

            transaction = TransactionModel(
                bot_id=bot_id,

                transaction_type=(
                    transaction_type
                ),

                status="COMPLETED",

                source_user_id=None,
                target_user_id=target.id,

                credits=amount,

                target_previous_balance=(
                    previous_balance
                ),

                target_final_balance=(
                    target.credits
                ),

                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),

                performed_by_role=(
                    performed_by_role
                ),

                reference=(
                    self._new_reference()
                ),

                description=description,
            )

            session.add(
                transaction
            )

            await session.commit()

            await session.refresh(
                transaction
            )

            return transaction

        except Exception:
            await session.rollback()
            raise


    # =====================================================
    # QUITAR CRÉDITOS
    # =====================================================

    async def remove_credits(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        target_user_id: int,
        amount: int,
        performed_by_telegram_id: int | None,
        performed_by_role: str | None,
        transaction_type: str = "CREDIT_REMOVE",
        description: str | None = None,
    ) -> TransactionModel:

        self._validate_amount(
            amount
        )

        actor_role = self._normalize_role(
            performed_by_role
        )

        if actor_role == "SELLER":
            raise UnauthorizedCreditOperationError(
                "SELLER no puede eliminar créditos. "
                "Debe utilizar una transferencia."
            )

        try:
            target = (
                await self._get_user_for_update(
                    session,
                    bot_id=bot_id,
                    user_id=target_user_id,
                )
            )

            if target.credits < amount:
                raise InsufficientCreditsError(
                    "El usuario no tiene "
                    "créditos suficientes."
                )

            previous_balance = int(
                target.credits
            )

            target.credits = (
                previous_balance
                - amount
            )

            transaction = TransactionModel(
                bot_id=bot_id,

                transaction_type=(
                    transaction_type
                ),

                status="COMPLETED",

                source_user_id=target.id,
                target_user_id=None,

                credits=amount,

                source_previous_balance=(
                    previous_balance
                ),

                source_final_balance=(
                    target.credits
                ),

                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),

                performed_by_role=(
                    performed_by_role
                ),

                reference=(
                    self._new_reference()
                ),

                description=description,
            )

            session.add(
                transaction
            )

            await session.commit()

            await session.refresh(
                transaction
            )

            return transaction

        except Exception:
            await session.rollback()
            raise


    # =====================================================
    # TRANSFERIR CRÉDITOS
    # =====================================================

    async def transfer_credits(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        source_user_id: int,
        target_user_id: int,
        amount: int,
        performed_by_telegram_id: int | None,
        performed_by_role: str | None,
        transaction_type: str = "CREDIT_TRANSFER",
        description: str | None = None,
    ) -> TransactionModel:

        self._validate_amount(
            amount
        )

        if (
            source_user_id
            == target_user_id
        ):
            raise CreditError(
                "No puedes transferirte "
                "créditos a ti mismo."
            )

        try:
            # Bloqueo ordenado para reducir
            # riesgo de deadlocks.
            first_id = min(
                source_user_id,
                target_user_id,
            )

            second_id = max(
                source_user_id,
                target_user_id,
            )

            first_user = (
                await self._get_user_for_update(
                    session,
                    bot_id=bot_id,
                    user_id=first_id,
                )
            )

            second_user = (
                await self._get_user_for_update(
                    session,
                    bot_id=bot_id,
                    user_id=second_id,
                )
            )

            if (
                first_user.id
                == source_user_id
            ):
                source = first_user
                target = second_user

            else:
                source = second_user
                target = first_user

            if (
                source.bot_id != bot_id
                or target.bot_id != bot_id
            ):
                raise CrossBotTransferError(
                    "No se permiten transferencias "
                    "entre bots distintos."
                )

            # Protección adicional específica
            # para SELLER.
            await self._validate_seller_transfer(
                session,
                bot_id=bot_id,
                source=source,
                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),
                performed_by_role=(
                    performed_by_role
                ),
            )

            if source.credits < amount:
                raise InsufficientCreditsError(
                    "Saldo insuficiente para "
                    "realizar la transferencia."
                )

            source_previous = int(
                source.credits
            )

            target_previous = int(
                target.credits
            )

            source.credits = (
                source_previous
                - amount
            )

            target.credits = (
                target_previous
                + amount
            )

            transaction = TransactionModel(
                bot_id=bot_id,

                transaction_type=(
                    transaction_type
                ),

                status="COMPLETED",

                source_user_id=source.id,
                target_user_id=target.id,

                credits=amount,

                source_previous_balance=(
                    source_previous
                ),

                source_final_balance=(
                    source.credits
                ),

                target_previous_balance=(
                    target_previous
                ),

                target_final_balance=(
                    target.credits
                ),

                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),

                performed_by_role=(
                    performed_by_role
                ),

                reference=(
                    self._new_reference()
                ),

                description=description,
            )

            session.add(
                transaction
            )

            await session.commit()

            await session.refresh(
                transaction
            )

            return transaction

        except Exception:
            await session.rollback()
            raise


    # =====================================================
    # COBRAR CONSULTA
    # =====================================================

    async def charge_query(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
        cost: int,
        command: str,
    ) -> TransactionModel | None:
        """
        Se llama únicamente DESPUÉS de validar
        correctamente los datos de entrada.

        cost=0 representa un CMD gratuito.
        """

        if (
            not isinstance(cost, int)
            or isinstance(cost, bool)
            or cost < 0
        ):
            raise InvalidCreditAmountError(
                "Costo de consulta inválido."
            )

        if cost == 0:
            return None

        return await self.remove_credits(
            session,

            bot_id=bot_id,

            target_user_id=(
                user_id
            ),

            amount=cost,

            performed_by_telegram_id=None,

            performed_by_role="SYSTEM",

            transaction_type=(
                "QUERY_CHARGE"
            ),

            description=(
                "Costo de consulta: "
                f"{command}"
            ),
        )


    # =====================================================
    # REEMBOLSO
    # =====================================================

    async def refund_query(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
        amount: int,
        command: str,
        reason: str,
    ) -> TransactionModel:

        return await self.add_credits(
            session,

            bot_id=bot_id,

            target_user_id=(
                user_id
            ),

            amount=amount,

            performed_by_telegram_id=None,

            performed_by_role="SYSTEM",

            transaction_type=(
                "QUERY_REFUND"
            ),

            description=(
                f"Reembolso {command}: "
                f"{reason}"
            ),
        )


credit_service = CreditService()
