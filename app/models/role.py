from __future__ import annotations

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
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database import Base


class RoleModel(Base):
    """
    Rol local de un usuario dentro de un bot.

    Los roles están completamente aislados
    mediante bot_id.

    Ejemplo:
    un Telegram ID puede ser OWNER en un bot
    y USER en otro.
    """

    __tablename__ = "roles"

    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "user_id",
            "role",
            name="uq_roles_bot_user_role",
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

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # ROL
    # =====================================================

    role: Mapped[str] = mapped_column(
        String(30),
        default="USER",
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # =====================================================
    # QUIÉN ASIGNÓ EL ROL
    # =====================================================

    assigned_by_telegram_id: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    assigned_by_role: Mapped[
        str | None
    ] = mapped_column(
        String(30),
        nullable=True,
    )

    # =====================================================
    # FECHAS
    # =====================================================

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    revoked_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # RELACIONES
    # =====================================================

    bot = relationship(
        "BotModel",
        back_populates="roles",
    )

    user = relationship(
        "UserModel",
        back_populates="roles",
    )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @property
    def normalized_role(self) -> str:
        return (
            self.role
            .strip()
            .upper()
        )

    @property
    def is_staff(self) -> bool:
        """
        Staff administrativo.

        SELLER queda fuera porque solamente
        puede vender/transferir créditos.
        """

        return (
            self.is_active
            and self.normalized_role
            in {
                "SUPERADMIN",
                "OWNER",
                "FUNDADOR",
                "COFUNDADOR",
                "ADMIN",
            }
        )

    @property
    def is_seller(self) -> bool:
        return (
            self.is_active
            and self.normalized_role
            == "SELLER"
        )

    @property
    def is_management(self) -> bool:
        return (
            self.is_active
            and self.normalized_role
            in {
                "SUPERADMIN",
                "OWNER",
                "FUNDADOR",
                "COFUNDADOR",
            }
        )

    def __repr__(self) -> str:
        return (
            "<RoleModel "
            f"id={self.id} "
            f"bot_id={self.bot_id} "
            f"user_id={self.user_id} "
            f"role={self.role!r} "
            f"active={self.is_active}>"
        )
