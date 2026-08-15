from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TransactionModel(Base):
    """
    Registra los movimientos económicos y de créditos
    realizados dentro de cada bot.

    Ejemplos:
    - CREDIT_ADD
    - CREDIT_REMOVE
    - CREDIT_TRANSFER
    - SELLER_TRANSFER
    - PLAN_PURCHASE
    - MANUAL_ADJUSTMENT

    Cada operación queda aislada mediante bot_id.
    """

    __tablename__ = "transactions"

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

    # =====================================================
    # TIPO DE OPERACIÓN
    # =====================================================

    transaction_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="COMPLETED",
        nullable=False,
        index=True,
    )

    # =====================================================
    # USUARIO ORIGEN
    # =====================================================

    source_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # USUARIO DESTINO
    # =====================================================

    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # CRÉDITOS
    # =====================================================

    credits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    source_previous_balance: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_final_balance: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    target_previous_balance: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    target_final_balance: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # INFORMACIÓN MONETARIA
    # =====================================================

    money_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=10,
            scale=2,
        ),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="PEN",
        nullable=False,
    )

    # =====================================================
    # QUIÉN REALIZÓ LA OPERACIÓN
    # =====================================================

    performed_by_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    performed_by_role: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    # =====================================================
    # REFERENCIAS
    # =====================================================

    reference: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extra_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # =====================================================
    # FECHA
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # =====================================================
    # RELACIONES
    # =====================================================

    bot = relationship(
        "BotModel",
        back_populates="transactions",
    )

    source_user = relationship(
        "UserModel",
        foreign_keys=[source_user_id],
    )

    target_user = relationship(
        "UserModel",
        foreign_keys=[target_user_id],
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @property
    def is_completed(self) -> bool:
        return self.status.upper() == "COMPLETED"

    @property
    def is_credit_transfer(self) -> bool:
        return self.transaction_type.upper() in {
            "CREDIT_TRANSFER",
            "SELLER_TRANSFER",
        }

    def __repr__(self) -> str:
        return (
            f"<TransactionModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"type={self.transaction_type!r} "
            f"credits={self.credits} "
            f"status={self.status!r}>"
        )
