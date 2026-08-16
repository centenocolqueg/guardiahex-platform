from __future__ import annotations

import asyncio
import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.settings import SystemSettingModel


PROVIDER_SETTING_KEY = "provider_config"


# =========================================================
# RESULTADO NORMALIZADO
# =========================================================

@dataclass(slots=True)
class ProviderResult:
    """
    Resultado normalizado de una consulta
    al proveedor autorizado.
    """

    success: bool
    status_code: int
    data: Any = None
    message: str | None = None
    no_results: bool = False
    content_type: str | None = None


# =========================================================
# CONFIGURACIÓN RUNTIME
# =========================================================

@dataclass(slots=True)
class ProviderRuntimeConfig:
    enabled: bool
    base_url: str
    timeout: int


# =========================================================
# ERRORES
# =========================================================

class ProviderSecurityError(Exception):
    """La configuración de red no es segura."""


# =========================================================
# SERVICIO
# =========================================================

class FuentesDataService:
    """
    Adaptador central del proveedor.

    Configuración pública:
        PostgreSQL
        - enabled
        - base_url
        - timeout

    Credencial privada:
        .env
        - FUENTESDATA_TOKEN

    El token jamás se guarda en la configuración
    pública de PostgreSQL ni se devuelve al panel.
    """

    def __init__(self) -> None:
        self._runtime_config: (
            ProviderRuntimeConfig | None
        ) = None


    # =====================================================
    # CONFIGURACIÓN BASE
    # =====================================================

    def _settings_config(
        self,
    ) -> ProviderRuntimeConfig:

        return ProviderRuntimeConfig(
            enabled=(
                settings.fuentesdata_enabled
            ),
            base_url=(
                settings
                .fuentesdata_base_url
                .strip()
                .rstrip("/")
            ),
            timeout=(
                settings.fuentesdata_timeout
            ),
        )


    @staticmethod
    def _safe_timeout(
        value: Any,
        default: int,
    ) -> int:

        try:
            timeout = int(value)

        except (
            TypeError,
            ValueError,
        ):
            return default

        return max(
            5,
            min(
                timeout,
                120,
            ),
        )


    @staticmethod
    def _safe_bool(
        value: Any,
        default: bool,
    ) -> bool:

        if isinstance(
            value,
            bool,
        ):
            return value

        if isinstance(
            value,
            str,
        ):
            normalized = (
                value.strip().lower()
            )

            if normalized in {
                "true",
                "1",
                "yes",
                "on",
            }:
                return True

            if normalized in {
                "false",
                "0",
                "no",
                "off",
            }:
                return False

        if value is None:
            return default

        return bool(value)


    # =====================================================
    # CARGAR POSTGRESQL
    # =====================================================

    async def load_config(
        self,
        session: AsyncSession,
    ) -> ProviderRuntimeConfig:
        """
        Lee PostgreSQL y actualiza la configuración
        en memoria del proceso.
        """

        fallback = (
            self._settings_config()
        )

        result = await session.execute(
            select(
                SystemSettingModel
            ).where(
                SystemSettingModel.key
                == PROVIDER_SETTING_KEY
            )
        )

        setting = (
            result.scalar_one_or_none()
        )

        if (
            setting is None
            or not setting.is_active
        ):
            self._runtime_config = fallback

            return fallback

        value = setting.value

        if not isinstance(
            value,
            dict,
        ):
            value = {}

        base_url = str(
            value.get(
                "base_url",
                fallback.base_url,
            )
            or ""
        ).strip().rstrip("/")

        config = ProviderRuntimeConfig(
            enabled=self._safe_bool(
                value.get(
                    "enabled"
                ),
                fallback.enabled,
            ),
            base_url=base_url,
            timeout=self._safe_timeout(
                value.get(
                    "timeout"
                ),
                fallback.timeout,
            ),
        )

        self._runtime_config = config

        return config


    async def refresh(
        self,
        session: AsyncSession,
    ) -> ProviderRuntimeConfig:
        """
        Alias explícito utilizado después
        de modificar la configuración.
        """

        return await self.load_config(
            session
        )


    async def _resolve_config(
        self,
        session: AsyncSession | None = None,
    ) -> ProviderRuntimeConfig:
        """
        Si hay sesión, obtiene la configuración
        más reciente desde PostgreSQL.

        Sin sesión utiliza la última configuración
        cargada en memoria.
        """

        if session is not None:
            return await self.load_config(
                session
            )

        if self._runtime_config is not None:
            return self._runtime_config

        return self._settings_config()


    # =====================================================
    # ESTADO
    # =====================================================

    @property
    def enabled(self) -> bool:
        """
        Compatibilidad con código existente.

        Para obtener configuración PostgreSQL
        actualizada usar load_config()/refresh().
        """

        config = (
            self._runtime_config
            or self._settings_config()
        )

        return bool(
            config.enabled
            and config.base_url
            and settings.fuentesdata_token.strip()
        )


    # =====================================================
    # SEGURIDAD URL
    # =====================================================

    @staticmethod
    def _validate_base_url(
        base_url: str,
    ) -> str:

        value = (
            base_url
            .strip()
            .rstrip("/")
        )

        if not value:
            raise ProviderSecurityError(
                "URL del proveedor no configurada."
            )

        parsed = urlparse(
            value
        )

        if parsed.scheme not in {
            "http",
            "https",
        }:
            raise ProviderSecurityError(
                "Esquema de URL inválido."
            )

        if (
            settings.is_production
            and parsed.scheme != "https"
        ):
            raise ProviderSecurityError(
                "El proveedor debe utilizar HTTPS."
            )

        hostname = (
            parsed.hostname
            or ""
        ).lower()

        if not hostname:
            raise ProviderSecurityError(
                "Host del proveedor inválido."
            )

        if hostname in {
            "localhost",
            "localhost.localdomain",
        }:
            raise ProviderSecurityError(
                "Host local no permitido."
            )

        try:
            ip = ipaddress.ip_address(
                hostname
            )

        except ValueError:
            # Es un dominio.
            return value

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_unspecified
            or ip.is_multicast
        ):
            raise ProviderSecurityError(
                "Dirección de red no permitida."
            )

        return value


    async def _verify_public_dns(
        self,
        base_url: str,
    ) -> None:
        """
        Si se configuró un dominio, comprueba
        que no resuelva hacia redes internas.
        """

        parsed = urlparse(
            base_url
        )

        hostname = (
            parsed.hostname
            or ""
        )

        if not hostname:
            raise ProviderSecurityError(
                "Host inválido."
            )

        try:
            ipaddress.ip_address(
                hostname
            )

            # Ya fue comprobada como IP literal.
            return

        except ValueError:
            pass

        try:
            loop = asyncio.get_running_loop()

            addresses = (
                await loop.getaddrinfo(
                    hostname,
                    parsed.port
                    or (
                        443
                        if parsed.scheme
                        == "https"
                        else 80
                    ),
                    type=0,
                )
            )

        except OSError as exc:
            raise ProviderSecurityError(
                "No se pudo resolver "
                "el dominio del proveedor."
            ) from exc

        if not addresses:
            raise ProviderSecurityError(
                "El dominio no resolvió "
                "ninguna dirección."
            )

        for address in addresses:

            raw_ip = address[4][0]

            try:
                ip = ipaddress.ip_address(
                    raw_ip
                )

            except ValueError:
                continue

            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
                or ip.is_multicast
            ):
                raise ProviderSecurityError(
                    "El dominio del proveedor "
                    "resuelve hacia una red "
                    "no permitida."
                )


    # =====================================================
    # ENDPOINT INTERNO
    # =====================================================

    @staticmethod
    def _validate_endpoint(
        endpoint: str,
    ) -> str:

        value = endpoint.strip()

        if not value:
            raise ValueError(
                "Endpoint no configurado."
            )

        lowered = value.lower()

        if (
            lowered.startswith(
                "http://"
            )
            or lowered.startswith(
                "https://"
            )
            or value.startswith("//")
            or "\\" in value
            or "?" in value
            or "#" in value
        ):
            raise ValueError(
                "Endpoint inválido."
            )

        segments = [
            segment
            for segment in value.split("/")
            if segment
        ]

        if ".." in segments:
            raise ValueError(
                "Endpoint inválido."
            )

        return value.lstrip("/")


    # =====================================================
    # HEADERS
    # =====================================================

    def _headers(
        self,
    ) -> dict[str, str]:
        """
        La forma exacta de autenticación puede
        ajustarse cuando exista documentación
        contractual del proveedor.
        """

        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "GUARDIAHEXBOT/1.0"
            ),
        }

        token = (
            settings
            .fuentesdata_token
            .strip()
        )

        if token:
            headers[
                "Authorization"
            ] = f"Bearer {token}"

        return headers


    # =====================================================
    # HEALTHCHECK LOCAL
    # =====================================================

    async def healthcheck(
        self,
        session: AsyncSession | None = None,
    ) -> ProviderResult:

        config = await self._resolve_config(
            session
        )

        token_configured = bool(
            settings
            .fuentesdata_token
            .strip()
        )

        ready = bool(
            config.enabled
            and config.base_url
            and token_configured
        )

        if not ready:
            return ProviderResult(
                success=False,
                status_code=503,
                message=(
                    "API no configurada."
                ),
            )

        try:
            base_url = (
                self._validate_base_url(
                    config.base_url
                )
            )

            await self._verify_public_dns(
                base_url
            )

        except ProviderSecurityError:
            return ProviderResult(
                success=False,
                status_code=400,
                message=(
                    "Configuración de API inválida."
                ),
            )

        return ProviderResult(
            success=True,
            status_code=200,
            message=(
                "Configuración API disponible."
            ),
        )


    # =====================================================
    # REQUEST
    # =====================================================

    async def request(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> ProviderResult:

        config = await self._resolve_config(
            session
        )

        token = (
            settings
            .fuentesdata_token
            .strip()
        )

        if not (
            config.enabled
            and config.base_url
            and token
        ):
            return ProviderResult(
                success=False,
                status_code=503,
                message=(
                    "Servicio no configurado."
                ),
            )

        try:
            base_url = (
                self._validate_base_url(
                    config.base_url
                )
            )

            await self._verify_public_dns(
                base_url
            )

            safe_endpoint = (
                self._validate_endpoint(
                    endpoint
                )
            )

        except (
            ProviderSecurityError,
            ValueError,
        ):
            return ProviderResult(
                success=False,
                status_code=400,
                message=(
                    "Configuración de consulta "
                    "inválida."
                ),
            )

        url = (
            f"{base_url}/"
            f"{safe_endpoint}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=config.timeout,
                follow_redirects=False,
            ) as client:

                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=self._headers(),
                    params=params,
                    json=json_data,
                )

        except httpx.TimeoutException:
            return ProviderResult(
                success=False,
                status_code=504,
                message=(
                    "Tiempo de espera agotado."
                ),
            )

        except httpx.RequestError:
            return ProviderResult(
                success=False,
                status_code=502,
                message=(
                    "No fue posible conectar "
                    "con el servicio."
                ),
            )

        return self._normalize_response(
            response
        )


    # =====================================================
    # GET / POST
    # =====================================================

    async def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> ProviderResult:

        return await self.request(
            method="GET",
            endpoint=endpoint,
            params=params,
            session=session,
        )


    async def post(
        self,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> ProviderResult:

        return await self.request(
            method="POST",
            endpoint=endpoint,
            json_data=json_data,
            session=session,
        )


    # =====================================================
    # NORMALIZAR RESPUESTA
    # =====================================================

    def _normalize_response(
        self,
        response: httpx.Response,
    ) -> ProviderResult:

        content_type = (
            response.headers.get(
                "content-type",
                "",
            )
            .lower()
        )

        if response.status_code == 204:
            return ProviderResult(
                success=True,
                status_code=204,
                data=None,
                message="Sin resultados.",
                no_results=True,
                content_type=content_type,
            )

        if response.status_code >= 500:
            return ProviderResult(
                success=False,
                status_code=(
                    response.status_code
                ),
                message=(
                    "Error temporal del servicio."
                ),
                content_type=content_type,
            )

        if response.status_code >= 400:
            return ProviderResult(
                success=False,
                status_code=(
                    response.status_code
                ),
                message=(
                    "La solicitud fue rechazada."
                ),
                content_type=content_type,
            )

        if (
            "application/json"
            in content_type
        ):
            try:
                payload = response.json()

            except ValueError:
                return ProviderResult(
                    success=False,
                    status_code=502,
                    message=(
                        "Respuesta JSON inválida."
                    ),
                    content_type=content_type,
                )

            no_results = (
                self._detect_no_results(
                    payload
                )
            )

            return ProviderResult(
                success=True,
                status_code=(
                    response.status_code
                ),
                data=payload,
                message=(
                    "Sin resultados."
                    if no_results
                    else "Consulta completada."
                ),
                no_results=no_results,
                content_type=content_type,
            )

        # PDF, imagen u otro archivo permitido.
        return ProviderResult(
            success=True,
            status_code=response.status_code,
            data=response.content,
            message="Archivo recibido.",
            no_results=False,
            content_type=content_type,
        )


    # =====================================================
    # DETECTAR SIN RESULTADOS
    # =====================================================

    @staticmethod
    def _detect_no_results(
        payload: Any,
    ) -> bool:

        if payload in (
            None,
            "",
            [],
            {},
        ):
            return True

        if isinstance(
            payload,
            dict,
        ):
            for key in (
                "data",
                "results",
                "result",
            ):
                if (
                    key in payload
                    and payload[key]
                    in (
                        None,
                        "",
                        [],
                        {},
                    )
                ):
                    return True

        return False


fuentesdata_service = FuentesDataService()
