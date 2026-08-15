from datetime import datetime, timedelta, timezone
import secrets
import string
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


# ==========================================
# CONFIGURACIÓN DE SEGURIDAD
# ==========================================

ALGORITHM = "HS256"

password_context = CryptContext(
    schemes=["bcrypt_sha256"],
    deprecated="auto",
)


# ==========================================
# CONTRASEÑAS
# ==========================================

def hash_password(password: str) -> str:
    """
    Convierte una contraseña en un hash seguro.
    La contraseña original nunca debe guardarse.
    """
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    return password_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verifica si una contraseña coincide
    con el hash almacenado.
    """
    if not plain_password or not hashed_password:
        return False

    return password_context.verify(
        plain_password,
        hashed_password,
    )


def generate_temporary_password(length: int = 14) -> str:
    """
    Genera una contraseña temporal para
    las nuevas cuentas de socios.
    """
    if length < 12:
        length = 12

    alphabet = (
        string.ascii_letters
        + string.digits
        + "!@#$%*-_"
    )

    while True:
        password = "".join(
            secrets.choice(alphabet)
            for _ in range(length)
        )

        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%*-_" for c in password)
        ):
            return password


# ==========================================
# JWT / SESIONES
# ==========================================

def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Crea un token JWT firmado para iniciar sesión
    en el panel GUARDIAHEXBOT.
    """

    now = datetime.now(timezone.utc)

    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )

    expire = now + timedelta(minutes=minutes)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Valida y decodifica un JWT.

    Retorna None si el token no es válido,
    está vencido o fue alterado.
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )

        if payload.get("type") != "access":
            return None

        if not payload.get("sub"):
            return None

        return payload

    except JWTError:
        return None


# ==========================================
# UTILIDADES
# ==========================================

def create_random_token(length: int = 32) -> str:
    """
    Genera tokens aleatorios seguros para
    operaciones internas del sistema.
    """
    return secrets.token_urlsafe(length)
