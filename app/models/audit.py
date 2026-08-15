from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditModel(Base):
    """
    Registro permanente de actividad de GUARDIAHEXBOT.

    Sirve para auditar:
    - comandos;
    - cambios de roles;
    - créditos;
    - suscripciones;
    - encendido/apagado de bots;
    - cambios de configuración;
    - accesos al panel;
    - errores internos.

    Cada registro queda asociado al bot donde
    ocurrió la operación.
    """

    __tablename__ = "audits"

    # =====================================================
    # IDENTIFICACIÓN
    # =====================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    bot_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "bots.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # TRAZABILIDAD
    # =====================================================

    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        default="TELEGRAM",
        nullable=False,
        index=True,
    )

    # Ejemplos:
    # TELEGRAM
    # MASTER_PANEL
    # PARTNER_PANEL
    # SYSTEM
    # API

    # =====================================================
    # ACCIÓN
    # =====================================================

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        default="SYSTEM",
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # ACTOR
    # =====================================================

    actor_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    actor_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    actor_role: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    # =====================================================
    # DESTINO
    # =====================================================

    target_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    target_type: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    # Ejemplos:
    # USER
    # BOT
    # SELLER
    # COMMAND
    # PARTNER
    # SUBSCRIPTION

    # =====================================================
    # COMANDO / OPERACIÓN
    # =====================================================

    command: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    masked_argument: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Nunca necesitamos guardar en este campo
    # el argumento sensible completo.

    # =====================================================
    # RESULTADO
    # =====================================================

    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="COMPLETED",
        nullable=False,
        index=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # MÉTRICAS
    # =====================================================

    credits_charged: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # INFORMACIÓN ADICIONAL
    # =====================================================

    extra_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # =====================================================
    # PANEL WEB
    # =====================================================

    ip_address: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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
        back_populates="audits",
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @property
    def is_error(self) -> bool:
        return (
            not self.success
            or self.status.upper() == "ERROR"
        )

    @property
    def actor_label(self) -> str:
        if self.actor_username:
            username = self.actor_username.lstrip("@")
            return f"@{username}"

        if self.actor_telegram_id:
            return str(self.actor_telegram_id)

        return "SYSTEM"

    def __repr__(self) -> str:
        return (
            f"<AuditModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"action={self.action!r} "
            f"success={self.success}>"
        )
