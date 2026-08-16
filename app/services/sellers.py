from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.permissions import can_manage_sellers
from app.models.role import RoleModel
from app.models.transaction import TransactionModel
from app.models.user import UserModel
from app.services.credits import (
    CreditService,
    InsufficientCreditsError,
    InvalidCreditAmountError,
    UserNotFoundError,
    credit_service,
)


# =========================================================
# ERRORES
# =========================================================

class SellerError(Exception):
    """Error general del sistema SELLER."""


class SellerNotFoundError(SellerError):
    """El usuario no posee rol SELLER activo."""


class SellerAlreadyExistsError(SellerError):
    """El usuario ya posee rol SELLER activo."""


class SellerPermissionError(SellerError):
    """Operación SELLER no autorizada."""


class SellerAccountDisabledError(SellerError):
    """La cuenta SELLER está inactiva o bloqueada."""


# =========================================================
# SERVICIO
# =========================================================

class SellerService:
    """
    Administración de SELLERS.

    Reglas:

    - SELLER pertenece solamente a un bot.
    - SELLER nunca crea créditos.
    - SELLER solamente transfiere saldo propio.
    - No existen transferencias entre bots.
    - SELLER bloqueado/inactivo no puede operar.
    - Solo roles autorizados pueden asignar
      o retirar SELLERS.
    """

    def __init__(
        self,
        credits: CreditService,
    ) -> None:
        self.credits = credits


    # =====================================================
    # VALIDACIONES
    # =====================================================

    @staticmethod
    def _validate_amount(
        amount: int,
    ) -> None:

        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount <= 0
        ):
            raise InvalidCreditAmountError(
                "La cantidad de créditos debe "
                "ser un entero mayor que cero."
            )


    @staticmethod
    def _validate_manager_role(
        role: str,
    ) -> None:

        if not can_manage_sellers(role):
            raise SellerPermissionError(
                "Tu rol no puede administrar SELLERS."
            )


    # =====================================================
    # BUSCAR USUARIO
    # =====================================================

    async def get_user_by_telegram_id(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
    ) -> UserModel:

        result = await session.execute(
            select(
                UserModel
            ).where(
                UserModel.bot_id == bot_id,
                UserModel.telegram_id
                == telegram_id,
            )
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


    async def _get_user_for_update_by_telegram_id(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
    ) -> UserModel:
        """
        Utilizado al cambiar roles para evitar
        dos modificaciones simultáneas.
        """

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
            raise UserNotFoundError(
                "Usuario no encontrado "
                "dentro de este bot."
            )

        return user


    # =====================================================
    # ROL SELLER
    # =====================================================

    async def get_seller_role(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
    ) -> RoleModel | None:

        result = await session.execute(
            select(
                RoleModel
            ).where(
                RoleModel.bot_id == bot_id,
                RoleModel.user_id == user_id,
                RoleModel.role == "SELLER",
                RoleModel.is_active.is_(True),
            )
        )

        return (
            result.scalar_one_or_none()
        )


    async def is_seller(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
    ) -> bool:

        role = await self.get_seller_role(
            session,
            bot_id=bot_id,
            user_id=user_id,
        )

        return role is not None


    # =====================================================
    # /seller
    # =====================================================

    async def assign_seller(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        target_telegram_id: int,
        assigned_by_telegram_id: int,
        assigned_by_role: str,
    ) -> RoleModel:
        """
        Asigna SELLER a un usuario ya registrado.

        Ejemplo:

        /seller 123456789
        """

        self._validate_manager_role(
            assigned_by_role
        )

        target = (
            await self._get_user_for_update_by_telegram_id(
                session,
                bot_id=bot_id,
                telegram_id=target_telegram_id,
            )
        )

        if (
            not target.is_registered
            or not target.is_active
            or target.is_banned
        ):
            raise SellerAccountDisabledError(
                "El usuario no tiene una "
                "cuenta habilitada."
            )

        result = await session.execute(
            select(
                RoleModel
            ).where(
                RoleModel.bot_id == bot_id,
                RoleModel.user_id == target.id,
                RoleModel.role == "SELLER",
            )
        )

        role = (
            result.scalar_one_or_none()
        )

        try:
            if role is not None:

                if role.is_active:
                    raise SellerAlreadyExistsError(
                        "El usuario ya es SELLER."
                    )

                role.is_active = True
                role.revoked_at = None

                role.assigned_by_telegram_id = (
                    assigned_by_telegram_id
                )

                role.assigned_by_role = (
                    assigned_by_role
                    .strip()
                    .upper()
                )

                role.updated_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

            else:
                role = RoleModel(
                    bot_id=bot_id,
                    user_id=target.id,
                    role="SELLER",
                    is_active=True,

                    assigned_by_telegram_id=(
                        assigned_by_telegram_id
                    ),

                    assigned_by_role=(
                        assigned_by_role
                        .strip()
                        .upper()
                    ),
                )

                session.add(role)

            await session.commit()

            await session.refresh(
                role
            )

            return role

        except Exception:
            await session.rollback()
            raise


    # =====================================================
    # /unseller
    # =====================================================

    async def remove_seller(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        target_telegram_id: int,
        removed_by_role: str,
    ) -> RoleModel:
        """
        Retira el rol SELLER.

        El saldo del usuario permanece intacto.
        """

        self._validate_manager_role(
            removed_by_role
        )

        target = (
            await self._get_user_for_update_by_telegram_id(
                session,
                bot_id=bot_id,
                telegram_id=target_telegram_id,
            )
        )

        role = await self.get_seller_role(
            session,
            bot_id=bot_id,
            user_id=target.id,
        )

        if role is None:
            raise SellerNotFoundError(
                "El usuario no es SELLER."
            )

        try:
            role.is_active = False

            role.revoked_at = (
                datetime.now(
                    timezone.utc
                )
            )

            role.updated_at = (
                datetime.now(
                    timezone.utc
                )
            )

            await session.commit()

            await session.refresh(
                role
            )

            return role

        except Exception:
            await session.rollback()
            raise


    # =====================================================
    # /sellers
    # =====================================================

    async def list_sellers(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> list[UserModel]:
        """
        Lista solamente vendedores actualmente
        autorizados y con cuenta operativa.
        """

        result = await session.execute(
            select(
                UserModel
            )
            .join(
                RoleModel,
                (
                    RoleModel.user_id
                    == UserModel.id
                )
                & (
                    RoleModel.bot_id
                    == UserModel.bot_id
                ),
            )
            .where(
                UserModel.bot_id == bot_id,

                UserModel.is_registered.is_(True),

                UserModel.is_active.is_(True),

                UserModel.is_banned.is_(False),

                RoleModel.role == "SELLER",

                RoleModel.is_active.is_(True),
            )
            .order_by(
                UserModel.id.asc()
            )
        )

        return list(
            result
            .scalars()
            .unique()
            .all()
        )


    # =====================================================
    # SALDO SELLER
    # =====================================================

    async def get_seller_balance(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        seller_telegram_id: int,
    ) -> int:

        seller = (
            await self.get_user_by_telegram_id(
                session,
                bot_id=bot_id,
                telegram_id=(
                    seller_telegram_id
                ),
            )
        )

        role = await self.get_seller_role(
            session,
            bot_id=bot_id,
            user_id=seller.id,
        )

        if role is None:
            raise SellerNotFoundError(
                "No tienes rol SELLER activo."
            )

        if (
            not seller.is_registered
            or not seller.is_active
            or seller.is_banned
        ):
            raise SellerAccountDisabledError(
                "La cuenta SELLER no "
                "se encuentra habilitada."
            )

        return int(
            seller.credits
        )


    # =====================================================
    # SELLER → /cred
    # =====================================================

    async def transfer_from_seller(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        seller_telegram_id: int,
        target_telegram_id: int,
        amount: int,
    ) -> TransactionModel:
        """
        SELLER solamente entrega créditos
        existentes en su propio saldo.

        Ejemplo:

        saldo SELLER = 3200

        /cred 987654321 200

        nuevo saldo SELLER = 3000
        usuario destino = +200
        """

        self._validate_amount(
            amount
        )

        if (
            seller_telegram_id
            == target_telegram_id
        ):
            raise SellerPermissionError(
                "Un SELLER no puede transferirse "
                "créditos a sí mismo."
            )

        seller = (
            await self.get_user_by_telegram_id(
                session,
                bot_id=bot_id,
                telegram_id=(
                    seller_telegram_id
                ),
            )
        )

        target = (
            await self.get_user_by_telegram_id(
                session,
                bot_id=bot_id,
                telegram_id=(
                    target_telegram_id
                ),
            )
        )

        seller_role = (
            await self.get_seller_role(
                session,
                bot_id=bot_id,
                user_id=seller.id,
            )
        )

        if seller_role is None:
            raise SellerNotFoundError(
                "No tienes rol SELLER activo."
            )

        if (
            not seller.is_registered
            or not seller.is_active
            or seller.is_banned
        ):
            raise SellerAccountDisabledError(
                "La cuenta SELLER no "
                "se encuentra habilitada."
            )

        if (
            not target.is_registered
            or not target.is_active
            or target.is_banned
        ):
            raise SellerPermissionError(
                "El usuario destino no "
                "se encuentra habilitado."
            )

        # Comprobación rápida para mensaje amigable.
        # CreditService vuelve a comprobar el saldo
        # después de bloquear las filas.
        if seller.credits < amount:
            raise InsufficientCreditsError(
                "No tienes créditos suficientes "
                "para realizar esta transferencia."
            )

        return await self.credits.transfer_credits(
            session,

            bot_id=bot_id,

            source_user_id=(
                seller.id
            ),

            target_user_id=(
                target.id
            ),

            amount=amount,

            performed_by_telegram_id=(
                seller_telegram_id
            ),

            performed_by_role="SELLER",

            transaction_type=(
                "SELLER_TRANSFER"
            ),

            description=(
                "Transferencia de créditos "
                "realizada por SELLER."
            ),
        )


seller_service = SellerService(
    credits=credit_service
)
