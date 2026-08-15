from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SocioModel(Base):
    """
    Cuenta principal de un socio dentro de
    GUARDIAHEXBOT PLATFORM.

    Cada socio podrá tener su acceso al panel
    y uno o más bots asociados según la
    configuración del SUPERADMIN.
    """

    __tablename__ = "socios"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    telegram_id: Mapped[int | None] = mapped_column(
        nullable=True,
        unique=True,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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

    bots = relationship(
        "BotModel",
        back_populates="socio",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<SocioModel "
            f"id={self.id} "
            f"username={self.username!r} "
            f"active={self.is_active}>"
        )
