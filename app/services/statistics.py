from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditModel
from app.models.bot import BotModel
from app.models.plan import SubscriptionModel
from app.models.role import RoleModel
from app.models.transaction import TransactionModel
from app.models.user import UserModel


class StatisticsService:
    """
    Servicio central de estadísticas.

    Permite obtener métricas:
    - por cada bot;
    - globales para SUPERADMIN;
    - por periodos de tiempo.

    Cada socio verá únicamente las estadísticas
    correspondientes a su propio bot.
    """

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _period_start(
        days: int,
    ) -> datetime:
        days = max(1, int(days))

        return (
            datetime.now(timezone.utc)
            - timedelta(days=days)
        )

    # =====================================================
    # USUARIOS
    # =====================================================

    async def count_users(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> int:
        result = await session.execute(
            select(
                func.count(UserModel.id)
            ).where(
                UserModel.bot_id == bot_id
            )
        )

        return int(
            result.scalar_one() or 0
        )

    async def count_active_users(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> int:
        result = await session.execute(
            select(
                func.count(UserModel.id)
            ).where(
                UserModel.bot_id == bot_id,
                UserModel.is_active.is_(True),
                UserModel.is_banned.is_(False),
            )
        )

        return int(
            result.scalar_one() or 0
        )

    async def count_banned_users(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> int:
        result = await session.execute(
            select(
                func.count(UserModel.id)
            ).where(
                UserModel.bot_id == bot_id,
                UserModel.is_banned.is_(True),
            )
        )

        return int(
            result.scalar_one() or 0
        )

    # =====================================================
    # SELLERS
    # =====================================================

    async def count_sellers(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> int:
        result = await session.execute(
            select(
                func.count(RoleModel.id)
            ).where(
                RoleModel.bot_id == bot_id,
                RoleModel.role == "SELLER",
                RoleModel.is_active.is_(True),
            )
        )

        return int(
            result.scalar_one() or 0
        )

    # =====================================================
    # CONSULTAS
    # =====================================================

    async def query_statistics(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        days: int = 1,
    ) -> dict[str, int]:
        since = self._period_start(days)

        total_result = await session.execute(
            select(
                func.count(AuditModel.id)
            ).where(
                AuditModel.bot_id == bot_id,
                AuditModel.category == "QUERY",
                AuditModel.created_at >= since,
            )
        )

        success_result = await session.execute(
            select(
                func.count(AuditModel.id)
            ).where(
                AuditModel.bot_id == bot_id,
                AuditModel.category == "QUERY",
                AuditModel.success.is_(True),
                AuditModel.created_at >= since,
            )
        )

        error_result = await session.execute(
            select(
                func.count(AuditModel.id)
            ).where(
                AuditModel.bot_id == bot_id,
                AuditModel.category == "QUERY",
                AuditModel.success.is_(False),
                AuditModel.created_at >= since,
            )
        )

        credits_result = await session.execute(
            select(
                func.coalesce(
                    func.sum(
                        AuditModel.credits_charged
                    ),
                    0,
                )
            ).where(
                AuditModel.bot_id == bot_id,
                AuditModel.category == "QUERY",
                AuditModel.created_at >= since,
            )
        )

        return {
            "total": int(
                total_result.scalar_one() or 0
            ),
            "successful": int(
                success_result.scalar_one() or 0
            ),
            "errors": int(
                error_result.scalar_one() or 0
            ),
            "credits_consumed": int(
                credits_result.scalar_one() or 0
            ),
        }

    # =====================================================
    # CRÉDITOS EN CIRCULACIÓN
    # =====================================================

    async def total_user_credits(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> int:
        result = await session.execute(
            select(
                func.coalesce(
                    func.sum(UserModel.credits),
                    0,
                )
            ).where(
                UserModel.bot_id == bot_id
            )
        )

        return int(
            result.scalar_one() or 0
        )

    # =====================================================
    # MOVIMIENTOS DE CRÉDITOS
    # =====================================================

    async def transaction_statistics(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        days: int = 30,
    ) -> dict[str, int]:
        since = self._period_start(days)

        count_result = await session.execute(
            select(
                func.count(
                    TransactionModel.id
                )
            ).where(
                TransactionModel.bot_id == bot_id,
                TransactionModel.created_at >= since,
                TransactionModel.status == "COMPLETED",
            )
        )

        credits_result = await session.execute(
            select(
                func.coalesce(
                    func.sum(
                        TransactionModel.credits
                    ),
                    0,
                )
            ).where(
                TransactionModel.bot_id == bot_id,
                TransactionModel.created_at >= since,
                TransactionModel.status == "COMPLETED",
            )
        )

        seller_result = await session.execute(
            select(
                func.coalesce(
                    func.sum(
                        TransactionModel.credits
                    ),
                    0,
                )
            ).where(
                TransactionModel.bot_id == bot_id,
                TransactionModel.transaction_type
                == "SELLER_TRANSFER",
                TransactionModel.created_at >= since,
                TransactionModel.status == "COMPLETED",
            )
        )

        return {
            "transactions": int(
                count_result.scalar_one() or 0
            ),
            "credits_moved": int(
                credits_result.scalar_one() or 0
            ),
            "seller_credits_transferred": int(
                seller_result.scalar_one() or 0
            ),
        }

    # =====================================================
    # SUSCRIPCIONES
    # =====================================================

    async def subscription_statistics(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> dict[str, int]:
        now = self._utc_now()

        active_result = await session.execute(
            select(
                func.count(
                    SubscriptionModel.id
                )
            ).where(
                SubscriptionModel.bot_id == bot_id,
                SubscriptionModel.is_active.is_(True),
                SubscriptionModel.expires_at > now,
            )
        )

        total_result = await session.execute(
            select(
                func.count(
                    SubscriptionModel.id
                )
            ).where(
                SubscriptionModel.bot_id == bot_id
            )
        )

        return {
            "active": int(
                active_result.scalar_one() or 0
            ),
            "historical": int(
                total_result.scalar_one() or 0
            ),
        }

    # =====================================================
    # ERRORES
    # =====================================================

    async def count_recent_errors(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        days: int = 1,
    ) -> int:
        since = self._period_start(days)

        result = await session.execute(
            select(
                func.count(AuditModel.id)
            ).where(
                AuditModel.bot_id == bot_id,
                AuditModel.success.is_(False),
                AuditModel.created_at >= since,
            )
        )

        return int(
            result.scalar_one() or 0
        )

    # =====================================================
    # RESUMEN COMPLETO DE UN BOT
    # =====================================================

    async def get_bot_statistics(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> dict[str, Any]:
        bot_result = await session.execute(
            select(BotModel).where(
                BotModel.id == bot_id
            )
        )

        bot = bot_result.scalar_one_or_none()

        if bot is None:
            raise ValueError(
                "Bot no encontrado."
            )

        users = await self.count_users(
            session,
            bot_id=bot_id,
        )

        active_users = await self.count_active_users(
            session,
            bot_id=bot_id,
        )

        banned_users = await self.count_banned_users(
            session,
            bot_id=bot_id,
        )

        sellers = await self.count_sellers(
            session,
            bot_id=bot_id,
        )

        credits = await self.total_user_credits(
            session,
            bot_id=bot_id,
        )

        queries_today = await self.query_statistics(
            session,
            bot_id=bot_id,
            days=1,
        )

        queries_30d = await self.query_statistics(
            session,
            bot_id=bot_id,
            days=30,
        )

        transactions = (
            await self.transaction_statistics(
                session,
                bot_id=bot_id,
                days=30,
            )
        )

        subscriptions = (
            await self.subscription_statistics(
                session,
                bot_id=bot_id,
            )
        )

        recent_errors = (
            await self.count_recent_errors(
                session,
                bot_id=bot_id,
                days=1,
            )
        )

        return {
            "bot": {
                "id": bot.id,
                "username": bot.username,
                "display_name": bot.display_name,
                "version": bot.version,
                "enabled": bot.enabled,
                "maintenance": bot.maintenance,
            },

            "users": {
                "total": users,
                "active": active_users,
                "banned": banned_users,
                "sellers": sellers,
            },

            "credits": {
                "circulating": credits,
                **transactions,
            },

            "queries": {
                "today": queries_today,
                "last_30_days": queries_30d,
            },

            "subscriptions": subscriptions,

            "system": {
                "errors_today": recent_errors,
            },

            "generated_at": (
                self._utc_now().isoformat()
            ),
        }

    # =====================================================
    # ESTADÍSTICAS GLOBALES SUPERADMIN
    # =====================================================

    async def get_global_statistics(
        self,
        session: AsyncSession,
    ) -> dict[str, Any]:
        bots_result = await session.execute(
            select(
                func.count(BotModel.id)
            )
        )

        active_bots_result = await session.execute(
            select(
                func.count(BotModel.id)
            ).where(
                BotModel.enabled.is_(True)
            )
        )

        users_result = await session.execute(
            select(
                func.count(UserModel.id)
            )
        )

        credits_result = await session.execute(
            select(
                func.coalesce(
                    func.sum(UserModel.credits),
                    0,
                )
            )
        )

        sellers_result = await session.execute(
            select(
                func.count(RoleModel.id)
            ).where(
                RoleModel.role == "SELLER",
                RoleModel.is_active.is_(True),
            )
        )

        active_subscriptions_result = (
            await session.execute(
                select(
                    func.count(
                        SubscriptionModel.id
                    )
                ).where(
                    SubscriptionModel.is_active
                    .is_(True),
                    SubscriptionModel.expires_at
                    > self._utc_now(),
                )
            )
        )

        errors_today_result = await session.execute(
            select(
                func.count(AuditModel.id)
            ).where(
                AuditModel.success.is_(False),
                AuditModel.created_at
                >= self._period_start(1),
            )
        )

        return {
            "bots": {
                "total": int(
                    bots_result.scalar_one()
                    or 0
                ),
                "active": int(
                    active_bots_result.scalar_one()
                    or 0
                ),
            },

            "users": {
                "total": int(
                    users_result.scalar_one()
                    or 0
                ),
                "sellers": int(
                    sellers_result.scalar_one()
                    or 0
                ),
            },

            "credits": {
                "circulating": int(
                    credits_result.scalar_one()
                    or 0
                ),
            },

            "subscriptions": {
                "active": int(
                    active_subscriptions_result
                    .scalar_one()
                    or 0
                ),
            },

            "system": {
                "errors_today": int(
                    errors_today_result
                    .scalar_one()
                    or 0
                ),
            },

            "generated_at": (
                self._utc_now().isoformat()
            ),
        }


statistics_service = StatisticsService()
