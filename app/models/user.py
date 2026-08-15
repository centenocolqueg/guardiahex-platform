from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserModel(Base):
    """
    Usuario registrado dentro de un bot.

    IMPORTANTE:
    El mismo Telegram ID puede existir en varios bots,
    pero sus créditos, roles, plan y estado permanecen
    completamente separados mediante bot_id.
    """

    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "telegram_id",
            name="uq_users_bot_telegram",
        ),
    )

    # =====================================================
    # IDENTIFICACIÓN INTERNA
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

    # =====================================================
    # TELEGRAM
    # =====================================================

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    # =====================================================
    # CUENTA
    # =====================================================

    credits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    current_plan: Mapped[str] = mapped_column(
        String(30),
        default="FREE",
        nullable=False,
        index=True,
    )

    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # REGISTRO / BONO
    # =====================================================

    is_registered: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    welcome_bonus_received: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # ESTADO
    # =====================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    is_banned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    ban_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    banned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # ESTADÍSTICAS
    # =====================================================

    total_queries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    successful_queries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    no_result_queries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_credits_spent: Mapped[int] = mapped_column(
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

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_query_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # RELACIONES
    # =====================================================

    bot = relationship(
        "BotModel",
        back_populates="users",
    )

    roles = relationship(
        "RoleModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @property
    def full_name(self) -> str:
        parts = [
            self.first_name,
            self.last_name,
        ]

        value = " ".join(
            part.strip()
            for part in parts
            if part and part.strip()
        )

        return value or "Usuario"

    @property
    def has_active_plan(self) -> bool:
        if self.current_plan.upper() == "FREE":
            return False

        if self.plan_expires_at is None:
            return True

        now = datetime.now(timezone.utc)

        return self.plan_expires_at > now

    def __repr__(self) -> str:
        return (
            f"<UserModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"telegram_id={self.telegram_id} "
            f"credits={self.credits}>"
        )
