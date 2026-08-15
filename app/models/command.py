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


class CommandModel(Base):
    """
    Catálogo maestro de comandos de GUARDIAHEXBOT.

    Aquí se define:
    - categoría;
    - comando;
    - nombre del servicio;
    - precio;
    - nivel;
    - versiones habilitadas;
    - tipo de resultado;
    - clave interna del proveedor.

    No se guardan URLs privadas ni tokens del
    proveedor dentro de este modelo.
    """

    __tablename__ = "commands"

    # =====================================================
    # IDENTIFICACIÓN
    # =====================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )

    command: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # NIVEL / PRECIO
    # =====================================================

    level: Mapped[str] = mapped_column(
        String(50),
        default="PROFESIONAL",
        nullable=False,
        index=True,
    )

    price: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # =====================================================
    # RESULTADO
    # =====================================================

    result_type: Mapped[str] = mapped_column(
        String(30),
        default="TEXT",
        nullable=False,
    )

    result_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Ejemplos posibles:
    # TEXT
    # IMAGE
    # PDF
    # FILE
    # MULTI
    # JSON
    output_formats: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # =====================================================
    # CONEXIÓN INTERNA
    # =====================================================

    provider_key: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    # =====================================================
    # VERSIONES
    # =====================================================

    available_versions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # =====================================================
    # CONTROL
    # =====================================================

    enabled_global: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    requires_registration: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    requires_authorization: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    charge_on_no_results: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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
    # CONFIGURACIONES POR BOT
    # =====================================================

    bot_configs = relationship(
        "BotCommandModel",
        back_populates="command_model",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    def available_for_version(
        self,
        version: str,
    ) -> bool:
        if not self.available_versions:
            return True

        version = version.strip().upper()

        return version in {
            item.upper()
            for item in self.available_versions
        }

    def __repr__(self) -> str:
        return (
            f"<CommandModel "
            f"id={self.id} "
            f"command={self.command!r} "
            f"category={self.category!r} "
            f"price={self.price}>"
        )


class BotCommandModel(Base):
    """
    Configuración individual de un CMD
    dentro de un bot específico.

    Permite al SUPERADMIN modificar un bot
    sin alterar el catálogo maestro.
    """

    __tablename__ = "bot_commands"

    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "command_id",
            name="uq_bot_commands_bot_command",
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

    command_id: Mapped[int] = mapped_column(
        ForeignKey(
            "commands.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # OVERRIDES
    # =====================================================

    enabled_override: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    price_override: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    level_override: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    title_override: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    result_description_override: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    command_model = relationship(
        "CommandModel",
        back_populates="bot_configs",
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    def effective_price(
        self,
        default_price: int,
    ) -> int:
        if self.price_override is not None:
            return self.price_override

        return default_price

    def effective_enabled(
        self,
        default_enabled: bool,
    ) -> bool:
        if self.enabled_override is not None:
            return self.enabled_override

        return default_enabled

    def __repr__(self) -> str:
        return (
            f"<BotCommandModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"command_id={self.command_id}>"
        )
