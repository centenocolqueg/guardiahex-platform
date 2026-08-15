from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlanModel(Base):
    """
    Plan comercial configurable de un bot.

    Tipos principales:
    - CREDITS
    - DAYS
    - SELLER

    Cada bot puede tener sus propios precios,
    beneficios y versiones habilitadas.
    """

    __tablename__ = "plans"

    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "code",
            name="uq_plans_bot_code",
        ),
    )

    # =====================================================
    # IDENTIFICACIÓN
    # =====================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    bot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "bots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # =====================================================
    # TIPO
    # =====================================================

    plan_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    level: Mapped[str] = mapped_column(
        String(50),
        default="PROFESIONAL",
        nullable=False,
    )

    # =====================================================
    # PRECIO
    # =====================================================

    price: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=10,
            scale=2,
        ),
        default=Decimal("0.00"),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="PEN",
        nullable=False,
    )

    # =====================================================
    # PLAN POR CRÉDITOS
    # =====================================================

    credits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    bonus_credits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # =====================================================
    # PLAN POR DÍAS
    # =====================================================

    days: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # =====================================================
    # SELLER
    # =====================================================

    seller_initial_credits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    grants_seller_role: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # VERSIONES DEL BOT
    # =====================================================

    available_versions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # =====================================================
    # ESTADO / ORDEN
    # =====================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # =====================================================
    # FECHAS
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # =====================================================
    # RELACIONES
    # =====================================================

    bot = relationship(
        "BotModel",
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @property
    def total_credits(self) -> int:
        return (
            self.credits
            + self.bonus_credits
        )

    def available_for_version(
        self,
        version: str,
    ) -> bool:
        if not self.available_versions:
            return True

        return version.upper() in {
            value.upper()
            for value in self.available_versions
        }

    def __repr__(self) -> str:
        return (
            f"<PlanModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"code={self.code!r} "
            f"type={self.plan_type!r}>"
        )


class SubscriptionModel(Base):
    """
    Historial de suscripciones por días.

    Los créditos y los días permanecen separados:
    /cred administra créditos.
    /sub administra suscripciones.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    bot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "bots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    plan_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    days_added: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    activated_by_telegram_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    activated_by_role: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    bot = relationship(
        "BotModel",
    )

    user = relationship(
        "UserModel",
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionModel "
            f"id={self.id} "
            f"user_id={self.user_id} "
            f"plan={self.plan_name!r}>"
        )
