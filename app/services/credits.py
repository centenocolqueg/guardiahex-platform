from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import TransactionModel
from app.models.user import UserModel


class CreditError(Exception):
    """Error general del sistema de créditos."""


class UserNotFoundError(CreditError):
    """El usuario no existe dentro del bot."""


class InsufficientCreditsError(CreditError):
    """El usuario no tiene créditos suficientes."""


class InvalidCreditAmountError(CreditError):
    """La cantidad de créditos no es válida."""


class CrossBotTransferError(CreditError):
    """
    Impide mover créditos entre usuarios
    pertenecientes a bots distintos.
    """


class CreditService:
    """
    Motor central de créditos de GUARDIAHEXBOT.

    Todas las operaciones se realizan por bot_id
    para mantener completamente aislados los saldos
    de cada bot de socio.
    """

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _validate_amount(amount: int) -> None:
        if not isinstance(amount, int):
            raise InvalidCreditAmountError(
                "La cantidad debe ser un número entero."
            )

        if amount <= 0:
            raise InvalidCreditAmountError(
                "La cantidad debe ser mayor que cero."
            )

    @staticmethod
    def _new_reference() -> str:
        return f"CR-{uuid.uuid4().hex.upper()}"

    # =====================================================
    # BUSCAR USUARIO CON BLOQUEO DE FILA
    # =====================================================

    async def _get_user_for_update(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
    ) -> UserModel:
        """
        Bloquea temporalmente la fila del usuario
        durante una operación de saldo.

        Esto ayuda a evitar problemas si dos
        movimientos intentan modificar el mismo
        saldo simultáneamente.
        """

        statement = (
            select(UserModel)
            .where(
                UserModel.id == user_id,
                UserModel.bot_id == bot_id,
            )
            .with_for_update()
        )

        result = await session.execute(statement)

        user = result.scalar_one_or_none()

        if user is None:
            raise UserNotFoundError(
                "Usuario no encontrado dentro de este bot."
            )

        return user

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
        statement = select(
            UserModel.credits
        ).where(
            UserModel.id == user_id,
            UserModel.bot_id == bot_id,
        )

        result = await session.execute(statement)

        balance = result.scalar_one_or_none()

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
        Añade créditos a un usuario.

        La autorización para crear créditos
        se comprobará antes de llamar este servicio.
        """

        self._validate_amount(amount)

        try:
            target = await self._get_user_for_update(
                session,
                bot_id=bot_id,
                user_id=target_user_id,
            )

            previous_balance = target.credits

            target.credits += amount

            transaction = TransactionModel(
                bot_id=bot_id,
                transaction_type=transaction_type,
                status="COMPLETED",

                source_user_id=None,
                target_user_id=target.id,

                credits=amount,

                target_previous_balance=previous_balance,
                target_final_balance=target.credits,

                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),
                performed_by_role=performed_by_role,

                reference=self._new_reference(),
                description=description,
            )

            session.add(transaction)

            await session.commit()
            await session.refresh(transaction)

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
        """
        Descuenta créditos de un usuario.

        Nunca permite dejar un saldo negativo.
        """

        self._validate_amount(amount)

        try:
            target = await self._get_user_for_update(
                session,
                bot_id=bot_id,
                user_id=target_user_id,
            )

            if target.credits < amount:
                raise InsufficientCreditsError(
                    "El usuario no tiene créditos suficientes."
                )

            previous_balance = target.credits

            target.credits -= amount

            transaction = TransactionModel(
                bot_id=bot_id,
                transaction_type=transaction_type,
                status="COMPLETED",

                source_user_id=target.id,
                target_user_id=None,

                credits=amount,

                source_previous_balance=previous_balance,
                source_final_balance=target.credits,

                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),
                performed_by_role=performed_by_role,

                reference=self._new_reference(),
                description=description,
            )

            session.add(transaction)

            await session.commit()
            await session.refresh(transaction)

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
        """
        Transfiere créditos entre dos usuarios
        pertenecientes al mismo bot.

        Esta función será utilizada también por
        SELLER, pero sellers.py agregará las reglas
        específicas de permisos del vendedor.
        """

        self._validate_amount(amount)

        if source_user_id == target_user_id:
            raise CreditError(
                "No puedes transferirte créditos a ti mismo."
            )

        try:
            # Se bloquean en orden por ID para reducir
            # riesgo de bloqueos cruzados concurrentes.
            first_id = min(
                source_user_id,
                target_user_id,
            )

            second_id = max(
                source_user_id,
                target_user_id,
            )

            first_user = await self._get_user_for_update(
                session,
                bot_id=bot_id,
                user_id=first_id,
            )

            second_user = await self._get_user_for_update(
                session,
                bot_id=bot_id,
                user_id=second_id,
            )

            if first_user.id == source_user_id:
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
                    "No se permiten transferencias entre bots."
                )

            if source.credits < amount:
                raise InsufficientCreditsError(
                    "Saldo insuficiente para realizar "
                    "la transferencia."
                )

            source_previous = source.credits
            target_previous = target.credits

            source.credits -= amount
            target.credits += amount

            transaction = TransactionModel(
                bot_id=bot_id,
                transaction_type=transaction_type,
                status="COMPLETED",

                source_user_id=source.id,
                target_user_id=target.id,

                credits=amount,

                source_previous_balance=source_previous,
                source_final_balance=source.credits,

                target_previous_balance=target_previous,
                target_final_balance=target.credits,

                performed_by_telegram_id=(
                    performed_by_telegram_id
                ),
                performed_by_role=performed_by_role,

                reference=self._new_reference(),
                description=description,
            )

            session.add(transaction)

            await session.commit()
            await session.refresh(transaction)

            return transaction

        except Exception:
            await session.rollback()
            raise

    # =====================================================
    # COBRAR UNA CONSULTA
    # =====================================================

    async def charge_query(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
        cost: int,
        command: str,
    ) -> TransactionModel:
        """
        Descuenta el costo de una consulta.

        Debe llamarse únicamente después de validar
        correctamente el formato de entrada.
        """

        return await self.remove_credits(
            session,
            bot_id=bot_id,
            target_user_id=user_id,
            amount=cost,
            performed_by_telegram_id=None,
            performed_by_role="SYSTEM",
            transaction_type="QUERY_CHARGE",
            description=(
                f"Costo de consulta: {command}"
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
        """
        Permite devolver créditos cuando exista
        una causa interna que justifique el reembolso.
        """

        return await self.add_credits(
            session,
            bot_id=bot_id,
            target_user_id=user_id,
            amount=amount,
            performed_by_telegram_id=None,
            performed_by_role="SYSTEM",
            transaction_type="QUERY_REFUND",
            description=(
                f"Reembolso {command}: {reason}"
            ),
        )


credit_service = CreditService()
