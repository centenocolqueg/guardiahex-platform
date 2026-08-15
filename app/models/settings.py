from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# =========================================================
# CONFIGURACIÓN GLOBAL
# =========================================================

class SystemSettingModel(Base):
    """
    Configuraciones globales administradas únicamente
    por el SUPERADMIN.

    Ejemplos:
    - mantenimiento global;
    - límites generales;
    - mensajes del sistema;
    - configuración de registro;
    - opciones de seguridad;
    - estado de servicios.

    Los secretos reales como tokens o contraseñas
    deben almacenarse cifrados o mediante variables
    privadas del servidor.
    """

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    key: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    value: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_secret: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    updated_by_telegram_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

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

    def __repr__(self) -> str:
        return (
            f"<SystemSettingModel "
            f"id={self.id} "
            f"key={self.key!r}>"
        )


# =========================================================
# CONFIGURACIÓN PARTICULAR DE CADA BOT
# =========================================================

class BotSettingModel(Base):
    """
    Configuración independiente de cada bot.

    Permite guardar valores particulares sin que
    un socio afecte a otro bot.

    Ejemplos:
    - mensaje de bienvenida;
    - nombre de administración;
    - opciones visuales;
    - límites especiales;
    - configuración de compra;
    - comportamiento de comandos.
    """

    __tablename__ = "bot_settings"

    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "key",
            name="uq_bot_settings_bot_key",
        ),
    )

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

    key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    value: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_secret: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    editable_by_partner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    updated_by_telegram_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

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

    bot = relationship(
        "BotModel",
    )

    def __repr__(self) -> str:
        return (
            f"<BotSettingModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"key={self.key!r}>"
        )
