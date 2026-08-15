from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_superadmin,
)
from app.database import get_db
from app.models.socio import SocioModel
from app.security import (
    generate_temporary_password,
    hash_password,
)


router = APIRouter(
    prefix="/socios",
    tags=["Socios"],
)


# =========================================================
# SCHEMAS
# =========================================================

class SocioCreateRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=80,
    )

    display_name: str = Field(
        min_length=2,
        max_length=120,
    )

    telegram_id: int | None = None

    email: str | None = Field(
        default=None,
        max_length=160,
    )

    password: str | None = Field(
        default=None,
        min_length=12,
        max_length=200,
    )


class SocioUpdateRequest(BaseModel):
    display_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    telegram_id: int | None = None

    email: str | None = Field(
        default=None,
        max_length=160,
    )

    is_active: bool | None = None


class SocioResponse(BaseModel):
    id: int
    username: str
    display_name: str
    telegram_id: int | None
    email: str | None
    is_active: bool
    must_change_password: bool
    bots_count: int


class SocioCreatedResponse(SocioResponse):
    """
    La contraseña temporal únicamente se devuelve
    cuando el SUPERADMIN crea o restablece la cuenta.
    """

    temporary_password: str


class ResetPasswordResponse(BaseModel):
    socio_id: int
    username: str
    temporary_password: str
    must_change_password: bool


# =========================================================
# UTILIDADES
# =========================================================

def _normalize_username(
    username: str,
) -> str:
    value = username.strip().lower()

    if not value:
        raise HTTPException(
            status_code=400,
            detail="Username inválido.",
        )

    return value


def _normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


async def _get_socio(
    session: AsyncSession,
    socio_id: int,
) -> SocioModel:
    result = await session.execute(
        select(SocioModel).where(
            SocioModel.id == socio_id
        )
    )

    socio = result.scalar_one_or_none()

    if socio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Socio no encontrado.",
        )

    return socio


def _to_response(
    socio: SocioModel,
) -> SocioResponse:
    return SocioResponse(
        id=socio.id,
        username=socio.username,
        display_name=socio.display_name,
        telegram_id=socio.telegram_id,
        email=socio.email,
        is_active=socio.is_active,
        must_change_password=(
            socio.must_change_password
        ),
        bots_count=len(socio.bots),
    )


# =========================================================
# CREAR SOCIO
# =========================================================

@router.post(
    "",
    response_model=SocioCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_socio(
    data: SocioCreateRequest,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> SocioCreatedResponse:
    """
    Crea una cuenta de socio.

    Solo el SUPERADMIN puede ejecutar
    esta operación.
    """

    username = _normalize_username(
        data.username
    )

    existing_result = await session.execute(
        select(SocioModel.id).where(
            func.lower(SocioModel.username)
            == username
        )
    )

    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Ese username ya está registrado."
            ),
        )

    if data.telegram_id is not None:
        telegram_result = await session.execute(
            select(SocioModel.id).where(
                SocioModel.telegram_id
                == data.telegram_id
            )
        )

        if telegram_result.scalar_one_or_none():
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Ese Telegram ID ya pertenece "
                    "a otro socio."
                ),
            )

    temporary_password = (
        data.password
        or generate_temporary_password()
    )

    socio = SocioModel(
        username=username,
        password_hash=hash_password(
            temporary_password
        ),
        display_name=(
            data.display_name.strip()
        ),
        telegram_id=data.telegram_id,
        email=_normalize_optional_text(
            data.email
        ),
        is_active=True,
        must_change_password=True,
    )

    session.add(socio)

    try:
        await session.commit()
        await session.refresh(socio)

    except Exception:
        await session.rollback()
        raise

    return SocioCreatedResponse(
        id=socio.id,
        username=socio.username,
        display_name=socio.display_name,
        telegram_id=socio.telegram_id,
        email=socio.email,
        is_active=socio.is_active,
        must_change_password=(
            socio.must_change_password
        ),
        bots_count=0,
        temporary_password=(
            temporary_password
        ),
    )


# =========================================================
# LISTAR SOCIOS
# =========================================================

@router.get(
    "",
    response_model=list[SocioResponse],
)
async def list_socios(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> list[SocioResponse]:
    result = await session.execute(
        select(SocioModel).order_by(
            SocioModel.id.desc()
        )
    )

    socios = list(
        result.scalars().unique().all()
    )

    return [
        _to_response(socio)
        for socio in socios
    ]


# =========================================================
# VER UN SOCIO
# =========================================================

@router.get(
    "/{socio_id}",
    response_model=SocioResponse,
)
async def get_socio(
    socio_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> SocioResponse:
    socio = await _get_socio(
        session,
        socio_id,
    )

    return _to_response(socio)


# =========================================================
# ACTUALIZAR SOCIO
# =========================================================

@router.patch(
    "/{socio_id}",
    response_model=SocioResponse,
)
async def update_socio(
    socio_id: int,
    data: SocioUpdateRequest,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> SocioResponse:
    socio = await _get_socio(
        session,
        socio_id,
    )

    if (
        data.telegram_id is not None
        and data.telegram_id
        != socio.telegram_id
    ):
        duplicate_result = (
            await session.execute(
                select(SocioModel.id).where(
                    SocioModel.telegram_id
                    == data.telegram_id,
                    SocioModel.id != socio.id,
                )
            )
        )

        if duplicate_result.scalar_one_or_none():
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Ese Telegram ID ya pertenece "
                    "a otro socio."
                ),
            )

    if data.display_name is not None:
        socio.display_name = (
            data.display_name.strip()
        )

    if data.telegram_id is not None:
        socio.telegram_id = (
            data.telegram_id
        )

    if data.email is not None:
        socio.email = (
            _normalize_optional_text(
                data.email
            )
        )

    if data.is_active is not None:
        socio.is_active = data.is_active

    try:
        await session.commit()
        await session.refresh(socio)

    except Exception:
        await session.rollback()
        raise

    return _to_response(socio)


# =========================================================
# ACTIVAR / DESACTIVAR
# =========================================================

@router.post(
    "/{socio_id}/enable",
    response_model=SocioResponse,
)
async def enable_socio(
    socio_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> SocioResponse:
    socio = await _get_socio(
        session,
        socio_id,
    )

    socio.is_active = True

    try:
        await session.commit()
        await session.refresh(socio)

    except Exception:
        await session.rollback()
        raise

    return _to_response(socio)


@router.post(
    "/{socio_id}/disable",
    response_model=SocioResponse,
)
async def disable_socio(
    socio_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> SocioResponse:
    """
    Bloquea el acceso del socio al panel.

    No borra su información ni sus bots.
    """

    socio = await _get_socio(
        session,
        socio_id,
    )

    socio.is_active = False

    try:
        await session.commit()
        await session.refresh(socio)

    except Exception:
        await session.rollback()
        raise

    return _to_response(socio)


# =========================================================
# RESTABLECER CONTRASEÑA
# =========================================================

@router.post(
    "/{socio_id}/reset-password",
    response_model=ResetPasswordResponse,
)
async def reset_socio_password(
    socio_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> ResetPasswordResponse:
    """
    Genera una nueva contraseña temporal.

    El hash queda en PostgreSQL.
    La contraseña temporal se muestra únicamente
    al SUPERADMIN en esta respuesta.
    """

    socio = await _get_socio(
        session,
        socio_id,
    )

    temporary_password = (
        generate_temporary_password()
    )

    socio.password_hash = hash_password(
        temporary_password
    )

    socio.must_change_password = True

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    return ResetPasswordResponse(
        socio_id=socio.id,
        username=socio.username,
        temporary_password=(
            temporary_password
        ),
        must_change_password=True,
    )
