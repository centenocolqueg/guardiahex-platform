from __future__ import annotations

import hmac
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

from app.config import settings
from app.database import get_db
from app.models.socio import SocioModel
from app.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)

security_scheme = HTTPBearer(
    auto_error=False,
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
        repr=False,
    )


class LoginResponse(BaseModel):
    access_token: str

    token_type: str = "bearer"

    account_type: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    role: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    socio_id: int | None = None

    display_name: str

    must_change_password: bool = False


class CurrentIdentity(BaseModel):
    """
    Identidad autenticada dentro del panel.
    """

    account_type: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    role: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    username: str

    socio_id: int | None = None

    display_name: str | None = None

    must_change_password: bool = False


# =========================================================
# ERRORES
# =========================================================

def invalid_credentials() -> HTTPException:
    """
    No revela si falló el usuario o la contraseña.
    """

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def invalid_session(
    detail: str = "Sesión inválida o expirada.",
) -> HTTPException:

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


# =========================================================
# LOGIN
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
    Entrada única para:

    - SUPERADMIN
    - PARTNER
    """

    username = data.username.strip()
    password = data.password

    if not username:
        raise invalid_credentials()

    # =====================================================
    # SUPERADMIN
    # =====================================================

    superadmin_username = (
        settings
        .superadmin_username
        .strip()
    )

    superadmin_password_hash = (
        settings
        .superadmin_password_hash
        .strip()
    )

    master_username_match = bool(
        superadmin_username
        and hmac.compare_digest(
            username.casefold(),
            superadmin_username.casefold(),
        )
    )

    if master_username_match:

        # Sin hash configurado en el VPS,
        # el acceso MASTER permanece bloqueado.
        if not superadmin_password_hash:
            raise invalid_credentials()

        if not verify_password(
            password,
            superadmin_password_hash,
        ):
            raise invalid_credentials()

        token = create_access_token(
            subject="superadmin",
            extra_claims={
                "account_type": "SUPERADMIN",
                "role": "SUPERADMIN",
                "username": superadmin_username,
            },
        )

        return LoginResponse(
            access_token=token,
            token_type="bearer",
            account_type="SUPERADMIN",
            role="SUPERADMIN",
            socio_id=None,
            display_name="SUPERADMIN",
            must_change_password=False,
        )

    # =====================================================
    # PARTNER
    # =====================================================

    result = await session.execute(
        select(
            SocioModel
        ).where(
            SocioModel.username == username,
            SocioModel.is_active.is_(True),
        )
    )

    socio = result.scalar_one_or_none()

    if socio is None:
        raise invalid_credentials()

    if not verify_password(
        password,
        socio.password_hash,
    ):
        raise invalid_credentials()

    token = create_access_token(
        subject=f"socio:{socio.id}",
        extra_claims={
            "account_type": "PARTNER",
            "role": "PARTNER",
            "socio_id": socio.id,
            "username": socio.username,
        },
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        account_type="PARTNER",
        role="PARTNER",
        socio_id=socio.id,
        display_name=socio.display_name,
        must_change_password=(
            socio.must_change_password
        ),
    )


# =========================================================
# TOKEN SUPERADMIN INTERNO
# =========================================================

def create_superadmin_panel_token(
    username: str | None = None,
) -> str:
    """
    Solo para procesos internos que ya hayan
    validado la identidad SUPERADMIN.
    """

    resolved_username = (
        username.strip()
        if username
        else settings.superadmin_username.strip()
    )

    if not resolved_username:
        resolved_username = "SUPERADMIN"

    return create_access_token(
        subject="superadmin",
        extra_claims={
            "account_type": "SUPERADMIN",
            "role": "SUPERADMIN",
            "username": resolved_username,
        },
    )


# =========================================================
# LEER SESIÓN
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

    if credentials is None:
        raise invalid_session(
            "Sesión no autenticada."
        )

    payload = decode_access_token(
        credentials.credentials
    )

    if payload is None:
        raise invalid_session()

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
            raise invalid_session(
                "Token MASTER inválido."
            )

        payload_role = str(
            payload.get(
                "role",
                "",
            )
        ).upper()

        if payload_role != "SUPERADMIN":
            raise invalid_session(
                "Rol MASTER inválido."
            )

        username = str(
            payload.get(
                "username",
                settings.superadmin_username,
            )
        ).strip()

        return CurrentIdentity(
            account_type="SUPERADMIN",
            role="SUPERADMIN",
            username=(
                username
                or "SUPERADMIN"
            ),
            socio_id=None,
            display_name="SUPERADMIN",
            must_change_password=False,
        )

    # =====================================================
    # PARTNER
    # =====================================================

    if account_type != "PARTNER":
        raise invalid_session(
            "Tipo de cuenta inválido."
        )

    if (
        str(
            payload.get(
                "role",
                "",
            )
        ).upper()
        != "PARTNER"
    ):
        raise invalid_session(
            "Rol de socio inválido."
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
    ) as exc:
        raise invalid_session(
            "Token de socio inválido."
        ) from exc

    expected_subject = (
        f"socio:{socio_id}"
    )

    if (
        payload.get("sub")
        != expected_subject
    ):
        raise invalid_session(
            "Token de socio inválido."
        )

    result = await session.execute(
        select(
            SocioModel
        ).where(
            SocioModel.id == socio_id,
            SocioModel.is_active.is_(True),
        )
    )

    socio = result.scalar_one_or_none()

    if socio is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "La cuenta del socio "
                "está deshabilitada."
            ),
        )

    return CurrentIdentity(
        account_type="PARTNER",
        role="PARTNER",
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

    if (
        identity.account_type
        != "SUPERADMIN"
        or identity.role
        != "SUPERADMIN"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Esta operación requiere "
                "permisos SUPERADMIN."
            ),
        )

    return identity


# =========================================================
# SOLO PARTNER
# =========================================================

async def require_partner(
    identity: Annotated[
        CurrentIdentity,
        Depends(get_current_identity),
    ],
) -> CurrentIdentity:

    if (
        identity.account_type
        != "PARTNER"
        or identity.role
        != "PARTNER"
        or identity.socio_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Esta operación requiere "
                "una cuenta de socio."
            ),
        )

    return identity


# =========================================================
# CUALQUIER CUENTA AUTENTICADA
# =========================================================

async def require_authenticated(
    identity: Annotated[
        CurrentIdentity,
        Depends(get_current_identity),
    ],
) -> CurrentIdentity:

    return identity


# =========================================================
# MI SESIÓN
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
