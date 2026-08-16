from __future__ import annotations

import hmac
import os
from typing import Annotated, Literal

from dotenv import load_dotenv
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


# =========================================================
# VARIABLES PRIVADAS
# =========================================================

load_dotenv()

SUPERADMIN_USERNAME = (
    os.getenv(
        "SUPERADMIN_USERNAME",
        "SUPERADMIN",
    )
    .strip()
)

SUPERADMIN_PASSWORD_HASH = (
    os.getenv(
        "SUPERADMIN_PASSWORD_HASH",
        "",
    )
    .strip()
)


# =========================================================
# ROUTER
# =========================================================

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

    # El frontend utiliza role para decidir
    # qué panel debe abrir.
    role: Literal[
        "SUPERADMIN",
        "PARTNER",
    ]

    socio_id: int | None = None

    display_name: str

    must_change_password: bool = False


class CurrentIdentity(BaseModel):
    """
    Identidad autenticada dentro de la plataforma.
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
# ERROR DE LOGIN
# =========================================================

def invalid_credentials() -> HTTPException:
    """
    Devuelve siempre el mismo error para evitar
    revelar si el usuario existe o no.
    """

    return HTTPException(
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
    Login único para:

    - SUPERADMIN
    - PARTNER

    Las contraseñas nunca se almacenan
    ni se comparan en texto plano.
    """

    username = (
        data.username
        .strip()
    )

    password = (
        data.password
    )


    # =====================================================
    # SUPERADMIN
    # =====================================================

    master_username_match = (
        hmac.compare_digest(
            username.casefold(),
            SUPERADMIN_USERNAME.casefold(),
        )
    )

    if master_username_match:

        # El SUPERADMIN no puede iniciar sesión
        # hasta configurar el hash en el VPS.
        if not SUPERADMIN_PASSWORD_HASH:
            raise invalid_credentials()

        if not verify_password(
            password,
            SUPERADMIN_PASSWORD_HASH,
        ):
            raise invalid_credentials()


        token = create_access_token(
            subject="superadmin",
            extra_claims={
                "account_type": (
                    "SUPERADMIN"
                ),
                "role": (
                    "SUPERADMIN"
                ),
                "username": (
                    SUPERADMIN_USERNAME
                ),
            },
        )


        return LoginResponse(
            access_token=token,
            token_type="bearer",
            account_type=(
                "SUPERADMIN"
            ),
            role=(
                "SUPERADMIN"
            ),
            socio_id=None,
            display_name=(
                "SUPERADMIN"
            ),
            must_change_password=False,
        )


    # =====================================================
    # SOCIO
    # =====================================================

    statement = (
        select(
            SocioModel
        )
        .where(
            SocioModel.username
            == username,

            SocioModel.is_active
            .is_(True),
        )
    )


    result = await session.execute(
        statement
    )

    socio = (
        result.scalar_one_or_none()
    )


    if socio is None:
        raise invalid_credentials()


    if not verify_password(
        password,
        socio.password_hash,
    ):
        raise invalid_credentials()


    token = create_access_token(
        subject=(
            f"socio:{socio.id}"
        ),
        extra_claims={
            "account_type": (
                "PARTNER"
            ),
            "role": (
                "PARTNER"
            ),
            "socio_id": (
                socio.id
            ),
            "username": (
                socio.username
            ),
        },
    )


    return LoginResponse(
        access_token=token,
        token_type="bearer",
        account_type="PARTNER",
        role="PARTNER",
        socio_id=socio.id,
        display_name=(
            socio.display_name
        ),
        must_change_password=(
            socio.must_change_password
        ),
    )


# =========================================================
# CREAR TOKEN SUPERADMIN INTERNAMENTE
# =========================================================

def create_superadmin_panel_token(
    username: str = "SUPERADMIN",
) -> str:
    """
    Genera un token SUPERADMIN para procesos
    internos que ya hayan validado la identidad.
    """

    return create_access_token(
        subject="superadmin",
        extra_claims={
            "account_type": (
                "SUPERADMIN"
            ),
            "role": (
                "SUPERADMIN"
            ),
            "username": (
                username
            ),
        },
    )


# =========================================================
# LEER TOKEN
# =========================================================

async def get_current_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials
        | None,
        Depends(
            security_scheme
        ),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CurrentIdentity:
    """
    Verifica JWT y reconstruye la identidad.
    """

    if credentials is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Sesión no autenticada."
            ),
            headers={
                "WWW-Authenticate": (
                    "Bearer"
                )
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
                "WWW-Authenticate": (
                    "Bearer"
                )
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

        if (
            payload.get("sub")
            != "superadmin"
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Token MASTER inválido."
                ),
            )


        username = str(
            payload.get(
                "username",
                SUPERADMIN_USERNAME,
            )
        )


        return CurrentIdentity(
            account_type=(
                "SUPERADMIN"
            ),
            role=(
                "SUPERADMIN"
            ),
            username=username,
            socio_id=None,
            display_name=(
                "SUPERADMIN"
            ),
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
            detail=(
                "Tipo de cuenta inválido."
            ),
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

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Token de socio inválido."
            ),
        ) from exc


    expected_subject = (
        f"socio:{socio_id}"
    )


    if (
        payload.get("sub")
        != expected_subject
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Token de socio inválido."
            ),
        )


    statement = (
        select(
            SocioModel
        )
        .where(
            SocioModel.id
            == socio_id,

            SocioModel.is_active
            .is_(True),
        )
    )


    result = await session.execute(
        statement
    )


    socio = (
        result.scalar_one_or_none()
    )


    if socio is None:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "La cuenta del socio "
                "está deshabilitada."
            ),
        )


    return CurrentIdentity(
        account_type="PARTNER",
        role="PARTNER",
        username=(
            socio.username
        ),
        socio_id=(
            socio.id
        ),
        display_name=(
            socio.display_name
        ),
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
        Depends(
            get_current_identity
        ),
    ],
) -> CurrentIdentity:

    if (
        identity.account_type
        != "SUPERADMIN"
    ):
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
        Depends(
            get_current_identity
        ),
    ],
) -> CurrentIdentity:

    if (
        identity.account_type
        != "PARTNER"
        or identity.socio_id
        is None
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
        Depends(
            get_current_identity
        ),
    ],
) -> CurrentIdentity:

    return identity


# =========================================================
# INFORMACIÓN DE SESIÓN
# =========================================================

@router.get(
    "/me",
    response_model=CurrentIdentity,
)
async def authenticated_account(
    identity: Annotated[
        CurrentIdentity,
        Depends(
            get_current_identity
        ),
    ],
) -> CurrentIdentity:

    return identity
