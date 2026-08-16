from __future__ import annotations

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
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database import Base


# =========================================================
# CATÁLOGO MAESTRO DE CMD
# =========================================================

class CommandModel(Base):
    """
    Catálogo maestro de comandos de GUARDIAHEXBOT.

    Define:

    - código interno;
    - categoría;
    - comando Telegram;
    - nombre del servicio;
    - costo en créditos;
    - nivel;
    - versiones habilitadas;
    - tipo de resultado;
    - formatos de salida;
    - clave interna del proveedor.

    Nunca guarda:
    - tokens;
    - claves API;
    - URLs privadas;
    - credenciales del proveedor.
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
    # NIVEL / COSTO
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
        index=True,
    )

    result_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Posibles formatos:
    #
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
    # PROVEEDOR
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
        default=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    # =====================================================
    # CONFIGURACIÓN POR BOT
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

    @property
    def normalized_code(self) -> str:
        return (
            str(self.code)
            .strip()
            .upper()
        )

    @property
    def normalized_category(self) -> str:
        return (
            str(self.category)
            .strip()
            .upper()
        )

    @property
    def normalized_command(self) -> str:
        """
        Devuelve el comando sin espacios
        y siempre con / al inicio.
        """

        value = (
            str(self.command)
            .strip()
            .lower()
        )

        if not value.startswith("/"):
            value = f"/{value}"

        return value

    @property
    def normalized_level(self) -> str:
        return (
            str(self.level)
            .strip()
            .upper()
        )

    @property
    def normalized_result_type(self) -> str:
        return (
            str(self.result_type)
            .strip()
            .upper()
        )

    @property
    def normalized_output_formats(
        self,
    ) -> list[str]:

        formats: list[str] = []

        for item in (
            self.output_formats
            or []
        ):

            value = (
                str(item)
                .strip()
                .upper()
            )

            if (
                value
                and value not in formats
            ):
                formats.append(
                    value
                )

        return formats

    def available_for_version(
        self,
        version: str,
    ) -> bool:
        """
        Fail-closed:

        Si no existen versiones configuradas,
        el comando NO queda habilitado.

        Esto evita que un CMD incompleto termine
        disponible accidentalmente en todos los bots.
        """

        if not self.available_versions:
            return False

        normalized_version = (
            str(version)
            .strip()
            .upper()
        )

        if normalized_version not in {
            "V1",
            "V2",
            "V3",
            "V4",
            "V5",
        }:
            return False

        allowed_versions = {
            str(item)
            .strip()
            .upper()

            for item
            in self.available_versions

            if str(item).strip()
        }

        return (
            normalized_version
            in allowed_versions
        )

    def effective_global_enabled(
        self,
        version: str,
    ) -> bool:
        """
        El CMD solo está globalmente disponible si:

        1. enabled_global = True
        2. pertenece a la versión solicitada
        """

        if not self.enabled_global:
            return False

        return self.available_for_version(
            version
        )

    def __repr__(self) -> str:
        return (
            "<CommandModel "
            f"id={self.id} "
            f"code={self.code!r} "
            f"command={self.command!r} "
            f"category={self.category!r} "
            f"price={self.price} "
            f"enabled={self.enabled_global}>"
        )


# =========================================================
# CONFIGURACIÓN CMD POR BOT
# =========================================================

class BotCommandModel(Base):
    """
    Override individual de un CMD para un bot.

    El SUPERADMIN puede modificar:

    - estado;
    - precio;
    - nivel;
    - título;
    - descripción.

    IMPORTANTE:

    Un override nunca puede activar un comando
    bloqueado globalmente o no disponible
    para la versión del bot.
    """

    __tablename__ = "bot_commands"

    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "command_id",
            name=(
                "uq_bot_commands_bot_command"
            ),
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

    enabled_override: Mapped[
        bool | None
    ] = mapped_column(
        Boolean,
        nullable=True,
    )

    price_override: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    level_override: Mapped[
        str | None
    ] = mapped_column(
        String(50),
        nullable=True,
    )

    title_override: Mapped[
        str | None
    ] = mapped_column(
        String(160),
        nullable=True,
    )

    result_description_override: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # FECHAS
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
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
        """
        Nunca devuelve precios negativos.
        """

        value = (
            self.price_override
            if self.price_override
            is not None
            else default_price
        )

        try:
            value = int(value)

        except (
            TypeError,
            ValueError,
        ):
            value = 0

        return max(
            0,
            value,
        )

    def effective_enabled(
        self,
        default_enabled: bool,
    ) -> bool:
        """
        Fail-closed.

        Si el comando maestro está OFF,
        ningún bot puede reactivarlo.

        Si está ON:
        - override False -> OFF
        - override True  -> ON
        - override None  -> ON
        """

        if not default_enabled:
            return False

        if self.enabled_override is False:
            return False

        return True

    def effective_level(
        self,
        default_level: str,
    ) -> str:

        value = (
            self.level_override
            if self.level_override
            is not None
            else default_level
        )

        return (
            str(value)
            .strip()
            .upper()
        )

    def effective_title(
        self,
        default_title: str,
    ) -> str:

        value = (
            self.title_override
            if self.title_override
            is not None
            else default_title
        )

        return (
            str(value)
            .strip()
        )

    def effective_result_description(
        self,
        default_description: str | None,
    ) -> str | None:

        value = (
            self.result_description_override
            if self.result_description_override
            is not None
            else default_description
        )

        if value is None:
            return None

        result = (
            str(value)
            .strip()
        )

        return (
            result
            or None
        )

    def __repr__(self) -> str:
        return (
            "<BotCommandModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"command_id={self.command_id} "
            f"enabled_override="
            f"{self.enabled_override}>"
        )
