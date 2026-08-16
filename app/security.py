from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import (
    Fernet,
    InvalidToken,
)
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

def hash_password(
    password: str,
) -> str:
    """
    Convierte una contraseña en un hash seguro.

    La contraseña original nunca debe
    guardarse en la base de datos.
    """

    if not password:
        raise ValueError(
            "La contraseña no puede estar vacía."
        )

    return password_context.hash(
        password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Comprueba una contraseña contra su hash.
    """

    if (
        not plain_password
        or not hashed_password
    ):
        return False

    try:
        return password_context.verify(
            plain_password,
            hashed_password,
        )

    except Exception:
        return False


def generate_temporary_password(
    length: int = 14,
) -> str:
    """
    Genera una contraseña temporal segura
    para una nueva cuenta de socio.
    """

    if length < 12:
        length = 12

    special_characters = (
        "!@#$%*-_"
    )

    alphabet = (
        string.ascii_letters
        + string.digits
        + special_characters
    )

    while True:

        password = "".join(
            secrets.choice(
                alphabet
            )
            for _ in range(
                length
            )
        )

        if (
            any(
                char.islower()
                for char in password
            )
            and any(
                char.isupper()
                for char in password
            )
            and any(
                char.isdigit()
                for char in password
            )
            and any(
                char
                in special_characters
                for char in password
            )
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
    Crea un JWT firmado para sesiones
    del panel GUARDIAHEXBOT.
    """

    now = datetime.now(
        timezone.utc
    )

    minutes = (
        expires_minutes
        if expires_minutes
        is not None
        else
        settings
        .access_token_expire_minutes
    )

    if minutes <= 0:
        raise ValueError(
            "La duración del token debe "
            "ser mayor a cero."
        )

    expire = (
        now
        + timedelta(
            minutes=minutes
        )
    )

    payload: dict[
        str,
        Any,
    ] = {
        "sub": str(
            subject
        ),
        "iat": int(
            now.timestamp()
        ),
        "exp": int(
            expire.timestamp()
        ),
        "type": "access",
    }

    if extra_claims:
        payload.update(
            extra_claims
        )

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Valida y decodifica un JWT.

    Retorna None cuando:
    - está vencido;
    - fue modificado;
    - tiene firma inválida;
    - no es un access token.
    """

    if not token:
        return None

    try:

        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[
                ALGORITHM
            ],
        )

        if (
            payload.get(
                "type"
            )
            != "access"
        ):
            return None

        if not payload.get(
            "sub"
        ):
            return None

        return payload

    except JWTError:
        return None


# ==========================================
# CIFRADO DE TOKENS TELEGRAM
# ==========================================

def get_bot_token_cipher() -> Fernet:
    """
    Obtiene el cifrador utilizado para
    proteger los tokens de BotFather.

    BOT_TOKEN_ENCRYPTION_KEY debe existir
    únicamente en el .env privado del VPS.
    """

    key = (
        settings
        .bot_token_encryption_key
        .strip()
    )

    if not key:
        raise RuntimeError(
            "BOT_TOKEN_ENCRYPTION_KEY "
            "no está configurada."
        )

    try:
        return Fernet(
            key.encode(
                "utf-8"
            )
        )

    except (
        ValueError,
        TypeError,
    ) as exc:

        raise RuntimeError(
            "BOT_TOKEN_ENCRYPTION_KEY "
            "no tiene un formato válido."
        ) from exc


def encrypt_bot_token(
    token: str,
) -> str:
    """
    Cifra un token de Telegram antes
    de guardarlo en PostgreSQL.
    """

    clean_token = (
        token.strip()
    )

    if not clean_token:
        raise ValueError(
            "El token del bot "
            "no puede estar vacío."
        )

    cipher = (
        get_bot_token_cipher()
    )

    encrypted = (
        cipher.encrypt(
            clean_token.encode(
                "utf-8"
            )
        )
    )

    return encrypted.decode(
        "utf-8"
    )


def decrypt_bot_token(
    encrypted_token: str,
) -> str:
    """
    Descifra un token solamente cuando
    el runtime necesita iniciar el bot.
    """

    clean_value = (
        encrypted_token.strip()
    )

    if not clean_value:
        raise ValueError(
            "No existe token cifrado."
        )

    cipher = (
        get_bot_token_cipher()
    )

    try:

        decrypted = (
            cipher.decrypt(
                clean_value.encode(
                    "utf-8"
                )
            )
        )

        return decrypted.decode(
            "utf-8"
        )

    except InvalidToken as exc:

        raise ValueError(
            "No se pudo descifrar "
            "el token del bot."
        ) from exc


def generate_bot_token_encryption_key() -> str:
    """
    Genera una nueva clave Fernet válida.

    Úsala una sola vez al configurar
    el VPS y guárdala en:

    BOT_TOKEN_ENCRYPTION_KEY=
    """

    return (
        Fernet.generate_key()
        .decode(
            "utf-8"
        )
    )


def mask_bot_token(
    token: str,
) -> str:
    """
    Devuelve una versión segura para logs
    o paneles sin exponer el token completo.
    """

    clean_token = (
        token.strip()
    )

    if not clean_token:
        return ""

    if ":" in clean_token:

        bot_id, secret = (
            clean_token.split(
                ":",
                1,
            )
        )

        visible_end = (
            secret[-4:]
            if len(secret) >= 4
            else "****"
        )

        return (
            f"{bot_id}:"
            f"********"
            f"{visible_end}"
        )

    if len(clean_token) <= 8:
        return "********"

    return (
        f"{clean_token[:4]}"
        f"********"
        f"{clean_token[-4:]}"
    )


# ==========================================
# TOKENS ALEATORIOS INTERNOS
# ==========================================

def create_random_token(
    length: int = 32,
) -> str:
    """
    Genera un valor criptográficamente
    aleatorio para operaciones internas.
    """

    if length < 16:
        length = 16

    return secrets.token_urlsafe(
        length
    )
