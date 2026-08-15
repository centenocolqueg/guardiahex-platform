from __future__ import annotations

import ipaddress
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_superadmin,
)
from app.config import settings
from app.database import get_db
from app.models.settings import SystemSettingModel
from app.services.audit import audit_service
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/provider",
    tags=["Proveedor API"],
)


PROVIDER_SETTING_KEY = "provider_config"


# =========================================================
# SCHEMAS
# =========================================================

class ProviderConfigRequest(BaseModel):
    enabled: bool | None = None

    base_url: str | None = Field(
        default=None,
        max_length=500,
    )

    timeout: int | None = Field(
        default=None,
        ge=5,
        le=120,
    )


class ProviderStatusResponse(BaseModel):
    enabled: bool

    base_url: str | None

    timeout: int

    token_configured: bool

    ready: bool

    provider_name: str = "FuentesData"


class ProviderTestResponse(BaseModel):
    success: bool

    reachable: bool

    status_code: int | None = None

    message: str

    latency_ms: int | None = None


# =========================================================
# UTILIDADES
# =========================================================

def _validate_base_url(
    value: str,
) -> str:
    """
    Valida la URL principal del proveedor.

    En producción exigimos HTTPS y rechazamos
    destinos locales o direcciones privadas.
    """

    value = value.strip().rstrip("/")

    if not value:
        raise HTTPException(
            status_code=400,
            detail="La URL base está vacía.",
        )

    parsed = urlparse(value)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "La URL debe comenzar con "
                "http:// o https://"
            ),
        )

    if (
        settings.is_production
        and parsed.scheme != "https"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "En producción la API "
                "debe utilizar HTTPS."
            ),
        )

    hostname = (
        parsed.hostname or ""
    ).lower()

    if not hostname:
        raise HTTPException(
            status_code=400,
            detail="Host de API inválido.",
        )

    if hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se permite utilizar "
                "un host local."
            ),
        )

    # Si el hostname es directamente una IP,
    # impedimos direcciones internas/privadas.
    try:
        ip = ipaddress.ip_address(
            hostname
        )

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se permite utilizar "
                    "una dirección IP privada."
                ),
            )

    except ValueError:
        # Es un dominio, no una IP literal.
        pass

    return value


async def _get_saved_config(
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Obtiene configuración pública del proveedor.

    El token secreto NO se almacena aquí.
    """

    result = await session.execute(
        select(SystemSettingModel).where(
            SystemSettingModel.key
            == PROVIDER_SETTING_KEY
        )
    )

    setting = result.scalar_one_or_none()

    if setting is None:
        return {
            "enabled": (
                settings.fuentesdata_enabled
            ),
            "base_url": (
                settings.fuentesdata_base_url
                or None
            ),
            "timeout": (
                settings.fuentesdata_timeout
            ),
        }

    value = setting.value or {}

    return {
        "enabled": bool(
            value.get(
                "enabled",
                settings.fuentesdata_enabled,
            )
        ),

        "base_url": (
            value.get("base_url")
            or settings.fuentesdata_base_url
            or None
        ),

        "timeout": int(
            value.get(
                "timeout",
                settings.fuentesdata_timeout,
            )
        ),
    }


async def _save_config(
    session: AsyncSession,
    *,
    config: dict[str, Any],
) -> None:
    result = await session.execute(
        select(SystemSettingModel).where(
            SystemSettingModel.key
            == PROVIDER_SETTING_KEY
        )
    )

    setting = result.scalar_one_or_none()

    if setting is None:
        setting = SystemSettingModel(
            key=PROVIDER_SETTING_KEY,
            value=config,
            description=(
                "Configuración pública del "
                "proveedor de consultas."
            ),
            is_secret=False,
            is_active=True,
        )

        session.add(setting)

    else:
        setting.value = config
        setting.is_active = True

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        raise


def _build_status(
    config: dict[str, Any],
) -> ProviderStatusResponse:
    enabled = bool(
        config.get("enabled")
    )

    base_url = (
        config.get("base_url")
    )

    timeout = int(
        config.get(
            "timeout",
            30,
        )
    )

    token_configured = bool(
        settings.fuentesdata_token
    )

    ready = bool(
        enabled
        and base_url
        and token_configured
    )

    return ProviderStatusResponse(
        enabled=enabled,
        base_url=base_url,
        timeout=timeout,
        token_configured=(
            token_configured
        ),
        ready=ready,
    )


# =========================================================
# ESTADO
# =========================================================

@router.get(
    "/status",
    response_model=ProviderStatusResponse,
)
async def provider_status(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> ProviderStatusResponse:
    """
    Muestra estado sin revelar el token.
    """

    config = await _get_saved_config(
        session
    )

    return _build_status(
        config
    )


# =========================================================
# CONFIGURACIÓN PÚBLICA
# =========================================================

@router.patch(
    "/config",
    response_model=ProviderStatusResponse,
)
async def update_provider_config(
    data: ProviderConfigRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> ProviderStatusResponse:
    """
    Permite al SUPERADMIN cambiar:

    - estado global ON/OFF;
    - URL base;
    - timeout.

    El token secreto permanece fuera de esta
    configuración y nunca se devuelve al navegador.
    """

    config = await _get_saved_config(
        session
    )

    fields = data.model_fields_set

    if (
        "enabled" in fields
        and data.enabled is not None
    ):
        config["enabled"] = (
            data.enabled
        )

    if "base_url" in fields:
        if data.base_url:
            config["base_url"] = (
                _validate_base_url(
                    data.base_url
                )
            )
        else:
            config["base_url"] = None

    if (
        "timeout" in fields
        and data.timeout is not None
    ):
        config["timeout"] = (
            data.timeout
        )

    await _save_config(
        session,
        config=config,
    )

    await audit_service.success(
        session,
        action="PROVIDER_CONFIG_UPDATED",
        category="PROVIDER",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        description=(
            "Configuración pública "
            "del proveedor actualizada."
        ),
        extra_data={
            "enabled": (
                config["enabled"]
            ),
            "base_url_configured": bool(
                config.get("base_url")
            ),
            "timeout": (
                config["timeout"]
            ),
        },
    )

    await realtime_service.publish_master(
        event_type=(
            "PROVIDER_CONFIG_CHANGED"
        ),
        data={
            "enabled": (
                config["enabled"]
            ),
            "ready": bool(
                config.get("enabled")
                and config.get("base_url")
                and settings.fuentesdata_token
            ),
        },
    )

    return _build_status(
        config
    )


# =========================================================
# PROBAR CONEXIÓN
# =========================================================

@router.post(
    "/test",
    response_model=ProviderTestResponse,
)
async def test_provider_connection(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> ProviderTestResponse:
    """
    Comprueba conectividad con el host configurado.

    No inventa rutas como /health.

    Una respuesta HTTP del host demuestra
    conectividad aunque el endpoint raíz responda
    401, 403 o 404.
    """

    config = await _get_saved_config(
        session
    )

    base_url = config.get(
        "base_url"
    )

    if not base_url:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Primero configura "
                "la URL base de la API."
            ),
        )

    base_url = _validate_base_url(
        base_url
    )

    timeout = int(
        config.get(
            "timeout",
            30,
        )
    )

    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "GUARDIAHEXBOT/1.0"
        ),
    }

    # Nunca devolvemos este valor al cliente.
    if settings.fuentesdata_token:
        headers["Authorization"] = (
            f"Bearer "
            f"{settings.fuentesdata_token}"
        )

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                base_url,
                headers=headers,
            )

            latency_ms = int(
                response.elapsed
                .total_seconds()
                * 1000
            )

        # Incluso 401/403/404 demuestra
        # que el servidor respondió.
        reachable = (
            response.status_code < 500
        )

        message = (
            "Servidor del proveedor accesible."
            if reachable
            else (
                "El proveedor respondió "
                "con un error del servidor."
            )
        )

        await audit_service.success(
            session,
            action="PROVIDER_CONNECTION_TEST",
            category="PROVIDER",
            source="MASTER_PANEL",
            actor_role="SUPERADMIN",
            description=message,
            extra_data={
                "status_code": (
                    response.status_code
                ),
                "latency_ms": (
                    latency_ms
                ),
            },
        )

        return ProviderTestResponse(
            success=reachable,
            reachable=reachable,
            status_code=(
                response.status_code
            ),
            message=message,
            latency_ms=latency_ms,
        )

    except httpx.TimeoutException:
        return ProviderTestResponse(
            success=False,
            reachable=False,
            status_code=None,
            message=(
                "La conexión superó "
                "el tiempo de espera."
            ),
            latency_ms=None,
        )

    except httpx.RequestError:
        return ProviderTestResponse(
            success=False,
            reachable=False,
            status_code=None,
            message=(
                "No fue posible conectar "
                "con el servidor configurado."
            ),
            latency_ms=None,
        )


# =========================================================
# INFORMACIÓN SEGURA
# =========================================================

@router.get("/info")
async def provider_info(
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> dict[str, Any]:
    """
    Información para la tarjeta API del
    dashboard MASTER.

    Nunca devuelve credenciales.
    """

    config = await _get_saved_config(
        session
    )

    status_data = _build_status(
        config
    )

    return {
        "provider": "FuentesData",
        "enabled": status_data.enabled,
        "ready": status_data.ready,
        "token_configured": (
            status_data.token_configured
        ),
        "base_url_configured": bool(
            status_data.base_url
        ),
        "timeout": (
            status_data.timeout
        ),
        "secret_visible": False,
    }
