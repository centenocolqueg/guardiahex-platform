from __future__ import annotations

from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.socio import SocioModel
from app.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)

security_scheme = HTTPBearer(
    auto_error=False
)


# =========================================================
# SCHEMAS
# =========================================================

class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=80,
    )

    password: str = Field(
        min_length=1,
        max_length=200,
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

    account_type: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    socio_id: int | None = None
    display_name: str
    must_change_password: bool = False


class CurrentIdentity(BaseModel):
    """
    Identidad autenticada dentro del panel.

    SUPERADMIN:
        acceso global.

    PARTNER:
        acceso limitado únicamente a su socio
        y a los bots asociados a ese socio.
    """

    account_type: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    username: str

    socio_id: int | None = None

    display_name: str | None = None

    must_change_password: bool = False


# =========================================================
# LOGIN DE SOCIOS
# =========================================================

@router.post(
    "/login",
    response_model=LoginResponse,
)
async def login(
    data: LoginRequest,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> LoginResponse:
    """
    Login del panel de socios.

    Las contraseñas se comparan únicamente
    contra su hash almacenado.
    """

    username = data.username.strip()

    statement = select(
        SocioModel
    ).where(
        SocioModel.username == username,
        SocioModel.is_active.is_(True),
    )

    result = await session.execute(
        statement
    )

    socio = result.scalar_one_or_none()

    if (
        socio is None
        or not verify_password(
            data.password,
            socio.password_hash,
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Usuario o contraseña incorrectos."
            ),
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    token = create_access_token(
        subject=f"socio:{socio.id}",
        extra_claims={
            "account_type": "PARTNER",
            "socio_id": socio.id,
            "username": socio.username,
        },
    )

    return LoginResponse(
        access_token=token,
        account_type="PARTNER",
        socio_id=socio.id,
        display_name=socio.display_name,
        must_change_password=(
            socio.must_change_password
        ),
    )


# =========================================================
# TOKEN INTERNO SUPERADMIN
# =========================================================

def create_superadmin_panel_token(
    username: str = "SUPERADMIN",
) -> str:
    """
    Genera el JWT del SUPERADMIN únicamente después
    de que la capa de autenticación MASTER haya
    validado sus credenciales.

    No expone una contraseña maestra en el código.
    """

    return create_access_token(
        subject="superadmin",
        extra_claims={
            "account_type": "SUPERADMIN",
            "username": username,
        },
    )


# =========================================================
# LEER TOKEN
# =========================================================

async def get_current_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security_scheme),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CurrentIdentity:
    """
    Valida el JWT y devuelve la identidad
    utilizada por las demás rutas del panel.
    """

    if credentials is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Sesión no autenticada.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    payload = decode_access_token(
        credentials.credentials
    )

    if payload is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Sesión inválida o expirada."
            ),
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    account_type = str(
        payload.get(
            "account_type",
            "",
        )
    ).upper()

    # =====================================================
    # SUPERADMIN
    # =====================================================

    if account_type == "SUPERADMIN":
        if payload.get("sub") != "superadmin":
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail="Token MASTER inválido.",
            )

        return CurrentIdentity(
            account_type="SUPERADMIN",
            username=str(
                payload.get(
                    "username",
                    "SUPERADMIN",
                )
            ),
            socio_id=None,
            display_name="SUPERADMIN",
            must_change_password=False,
        )

    # =====================================================
    # SOCIO
    # =====================================================

    if account_type != "PARTNER":
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Tipo de cuenta inválido.",
        )

    socio_id_raw = payload.get(
        "socio_id"
    )

    try:
        socio_id = int(
            socio_id_raw
        )
    except (
        TypeError,
        ValueError,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Token de socio inválido.",
        )

    expected_subject = (
        f"socio:{socio_id}"
    )

    if payload.get("sub") != expected_subject:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Token de socio inválido.",
        )

    statement = select(
        SocioModel
    ).where(
        SocioModel.id == socio_id,
        SocioModel.is_active.is_(True),
    )

    result = await session.execute(
        statement
    )

    socio = result.scalar_one_or_none()

    if socio is None:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "La cuenta del socio está deshabilitada."
            ),
        )

    return CurrentIdentity(
        account_type="PARTNER",
        username=socio.username,
        socio_id=socio.id,
        display_name=socio.display_name,
        must_change_password=(
            socio.must_change_password
        ),
    )


# =========================================================
# SOLO SUPERADMIN
# =========================================================

async def require_superadmin(
    identity: Annotated[
        CurrentIdentity,
        Depends(get_current_identity),
    ],
) -> CurrentIdentity:
    if identity.account_type != "SUPERADMIN":
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Esta operación requiere "
                "permisos SUPERADMIN."
            ),
        )

    return identity


# =========================================================
# SOLO SOCIO
# =========================================================

async def require_partner(
    identity: Annotated[
        CurrentIdentity,
        Depends(get_current_identity),
    ],
) -> CurrentIdentity:
    if (
        identity.account_type != "PARTNER"
        or identity.socio_id is None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Esta operación requiere "
                "una cuenta de socio."
            ),
        )

    return identity


# =========================================================
# SUPERADMIN O SOCIO
# =========================================================

async def require_authenticated(
    identity: Annotated[
        CurrentIdentity,
        Depends(get_current_identity),
    ],
) -> CurrentIdentity:
    return identity


# =========================================================
# INFORMACIÓN DE LA SESIÓN
# =========================================================

@router.get(
    "/me",
    response_model=CurrentIdentity,
)
async def authenticated_account(
    identity: Annotated[
        CurrentIdentity,
        Depends(get_current_identity),
    ],
) -> CurrentIdentity:
    return identity
