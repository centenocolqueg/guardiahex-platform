from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BotModel(Base):
    """
    Representa GUARDIAHEXBOT MASTER o
    un bot perteneciente a un socio.

    Cada bot mantiene de forma independiente:
    - identidad;
    - versión V1-V5;
    - estado ON/OFF;
    - token protegido;
    - grupo y canal;
    - grupos privados de auditoría;
    - usuarios;
    - configuración.
    """

    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # =====================================================
    # PROPIETARIO
    # =====================================================

    socio_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "socios.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # IDENTIDAD TELEGRAM
    # =====================================================

    telegram_bot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True,
        index=True,
    )

    username: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(120),
        default="GUARDIAHEXBOT",
        nullable=False,
    )

    administration_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    # El token real no debe guardarse públicamente
    # ni escribirse directamente en el repositorio.
    token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # TIPO / VERSIÓN
    # =====================================================

    is_master: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    version: Mapped[str] = mapped_column(
        String(10),
        default="V1",
        nullable=False,
        index=True,
    )

    # =====================================================
    # ESTADO
    # =====================================================

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    maintenance: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    maintenance_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # CANAL / GRUPO PÚBLICO
    # =====================================================

    channel_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    group_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # =====================================================
    # GRUPOS PRIVADOS DE LOGS
    # =====================================================

    history_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    sales_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # =====================================================
    # LÍMITES
    # =====================================================

    daily_query_limit: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        nullable=False,
    )

    max_founders: Mapped[int] = mapped_column(
        Integer,
        default=4,
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

    last_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # RELACIONES
    # =====================================================

    socio = relationship(
        "SocioModel",
        back_populates="bots",
    )

    users = relationship(
        "UserModel",
        back_populates="bot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    roles = relationship(
        "RoleModel",
        back_populates="bot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    transactions = relationship(
        "TransactionModel",
        back_populates="bot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    audits = relationship(
        "AuditModel",
        back_populates="bot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<BotModel "
            f"id={self.id} "
            f"username={self.username!r} "
            f"version={self.version!r} "
            f"enabled={self.enabled}>"
        )
