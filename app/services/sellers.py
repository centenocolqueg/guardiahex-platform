from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import RoleModel
from app.models.transaction import TransactionModel
from app.models.user import UserModel
from app.services.credits import (
    CreditService,
    InsufficientCreditsError,
    UserNotFoundError,
    credit_service,
)


class SellerError(Exception):
    """Error general del sistema SELLER."""


class SellerNotFoundError(SellerError):
    """El usuario no tiene rol SELLER activo."""


class SellerAlreadyExistsError(SellerError):
    """El usuario ya tiene rol SELLER."""


class SellerPermissionError(SellerError):
    """Operación SELLER no permitida."""


class SellerService:
    """
    Servicio encargado de administrar SELLERS.

    Reglas principales:
    - El SELLER pertenece únicamente a un bot.
    - No puede crear créditos.
    - Solo puede transferir desde su propio saldo.
    - No puede transferir créditos entre bots.
    - Todas las operaciones quedan registradas.
    """

    def __init__(
        self,
        credits: CreditService,
    ) -> None:
        self.credits = credits

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
            raise UserNotFoundError(
                "Usuario no encontrado dentro de este bot."
            )

        return user

    # =====================================================
    # COMPROBAR SELLER
    # =====================================================

    async def get_seller_role(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        user_id: int,
    ) -> RoleModel | None:
        statement = select(
            RoleModel
        ).where(
            RoleModel.bot_id == bot_id,
            RoleModel.user_id == user_id,
            RoleModel.role == "SELLER",
            RoleModel.is_active.is_(True),
        )

        result = await session.execute(
            statement
        )

        return result.scalar_one_or_none()

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
        Asigna el rol SELLER a un usuario registrado.

        Ejemplo:
        /seller 123456789
        """

        target = await self.get_user_by_telegram_id(
            session,
            bot_id=bot_id,
            telegram_id=target_telegram_id,
        )

        statement = select(
            RoleModel
        ).where(
            RoleModel.bot_id == bot_id,
            RoleModel.user_id == target.id,
            RoleModel.role == "SELLER",
        )

        result = await session.execute(
            statement
        )

        role = result.scalar_one_or_none()

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
                    assigned_by_role.upper()
                )
                role.updated_at = datetime.now(
                    timezone.utc
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
                        assigned_by_role.upper()
                    ),
                )

                session.add(role)

            await session.commit()
            await session.refresh(role)

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
    ) -> RoleModel:
        """
        Desactiva el rol SELLER.

        Los créditos del usuario permanecen intactos.
        """

        target = await self.get_user_by_telegram_id(
            session,
            bot_id=bot_id,
            telegram_id=target_telegram_id,
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
            role.revoked_at = datetime.now(
                timezone.utc
            )

            await session.commit()
            await session.refresh(role)

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
        Devuelve únicamente SELLERS activos
        pertenecientes al bot indicado.
        """

        statement = (
            select(UserModel)
            .join(
                RoleModel,
                RoleModel.user_id == UserModel.id,
            )
            .where(
                UserModel.bot_id == bot_id,
                RoleModel.bot_id == bot_id,
                RoleModel.role == "SELLER",
                RoleModel.is_active.is_(True),
            )
            .order_by(
                UserModel.id.asc()
            )
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().unique().all()
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
        seller = await self.get_user_by_telegram_id(
            session,
            bot_id=bot_id,
            telegram_id=seller_telegram_id,
        )

        if not await self.is_seller(
            session,
            bot_id=bot_id,
            user_id=seller.id,
        ):
            raise SellerNotFoundError(
                "No tienes rol SELLER activo."
            )

        return seller.credits

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
        Regla central del SELLER:

        El vendedor únicamente puede entregar
        créditos existentes en su propio saldo.

        Ejemplo:

        SELLER tiene 3200
        /cred 987654321 200

        SELLER queda con 3000
        usuario destino recibe +200
        """

        seller = await self.get_user_by_telegram_id(
            session,
            bot_id=bot_id,
            telegram_id=seller_telegram_id,
        )

        target = await self.get_user_by_telegram_id(
            session,
            bot_id=bot_id,
            telegram_id=target_telegram_id,
        )

        if seller.id == target.id:
            raise SellerPermissionError(
                "Un SELLER no puede transferirse "
                "créditos a sí mismo."
            )

        seller_role = await self.get_seller_role(
            session,
            bot_id=bot_id,
            user_id=seller.id,
        )

        if seller_role is None:
            raise SellerNotFoundError(
                "No tienes rol SELLER activo."
            )

        if not seller.is_active or seller.is_banned:
            raise SellerPermissionError(
                "La cuenta SELLER no está habilitada."
            )

        if not target.is_active or target.is_banned:
            raise SellerPermissionError(
                "El usuario destino no está habilitado."
            )

        if seller.credits < amount:
            raise InsufficientCreditsError(
                "No tienes créditos suficientes "
                "para realizar esta transferencia."
            )

        return await self.credits.transfer_credits(
            session,
            bot_id=bot_id,
            source_user_id=seller.id,
            target_user_id=target.id,
            amount=amount,
            performed_by_telegram_id=(
                seller_telegram_id
            ),
            performed_by_role="SELLER",
            transaction_type="SELLER_TRANSFER",
            description=(
                "Transferencia de créditos realizada "
                "por SELLER."
            ),
        )


seller_service = SellerService(
    credits=credit_service
)
