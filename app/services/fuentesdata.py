from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


@dataclass(slots=True)
class ProviderResult:
    """
    Resultado normalizado de una consulta al proveedor.

    El resto de GUARDIAHEXBOT no necesita conocer
    detalles internos del proveedor.
    """

    success: bool
    status_code: int
    data: Any = None
    message: str | None = None
    no_results: bool = False
    content_type: str | None = None


class FuentesDataService:
    """
    Adaptador central para la API autorizada.

    Por ahora permanece desactivado hasta contar
    con URL, token y documentación oficial.

    No se colocan credenciales ni endpoints privados
    directamente dentro del repositorio.
    """

    def __init__(self) -> None:
        self.base_url = settings.fuentesdata_base_url.rstrip("/")
        self.token = settings.fuentesdata_token
        self.timeout = settings.fuentesdata_timeout

    @property
    def enabled(self) -> bool:
        return settings.api_ready

    def _headers(self) -> dict[str, str]:
        """
        Cabeceras base.

        La estructura exacta de autenticación podrá
        ajustarse cuando tengamos la documentación
        oficial del proveedor.
        """

        headers = {
            "Accept": "application/json",
            "User-Agent": "GUARDIAHEXBOT/1.0",
        }

        if self.token:
            headers["Authorization"] = (
                f"Bearer {self.token}"
            )

        return headers

    async def healthcheck(self) -> ProviderResult:
        """
        Comprueba si la configuración de la API
        está disponible.

        No inventamos una ruta /health del proveedor.
        Mientras no tengamos documentación real,
        solo verificamos configuración local.
        """

        if not self.enabled:
            return ProviderResult(
                success=False,
                status_code=503,
                message="API no configurada.",
            )

        return ProviderResult(
            success=True,
            status_code=200,
            message="Configuración API disponible.",
        )

    async def request(
        self,
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """
        Ejecuta una petición genérica a un endpoint
        autorizado y previamente configurado.

        El endpoint deberá venir del catálogo interno
        aprobado por el SUPERADMIN.
        """

        if not self.enabled:
            return ProviderResult(
                success=False,
                status_code=503,
                message="Servicio no configurado.",
            )

        endpoint = endpoint.strip()

        if not endpoint:
            return ProviderResult(
                success=False,
                status_code=400,
                message="Endpoint no configurado.",
            )

        # Evita aceptar URLs externas arbitrarias.
        if endpoint.startswith(
            ("http://", "https://")
        ):
            return ProviderResult(
                success=False,
                status_code=400,
                message="Endpoint inválido.",
            )

        url = (
            f"{self.base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
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
                message="Tiempo de espera agotado.",
            )

        except httpx.RequestError:
            return ProviderResult(
                success=False,
                status_code=502,
                message="No fue posible conectar con el servicio.",
            )

        return self._normalize_response(
            response
        )

    async def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> ProviderResult:
        return await self.request(
            method="GET",
            endpoint=endpoint,
            params=params,
        )

    async def post(
        self,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
    ) -> ProviderResult:
        return await self.request(
            method="POST",
            endpoint=endpoint,
            json_data=json_data,
        )

    def _normalize_response(
        self,
        response: httpx.Response,
    ) -> ProviderResult:
        """
        Convierte la respuesta HTTP a un formato
        estándar para todo GUARDIAHEXBOT.
        """

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

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
                status_code=response.status_code,
                message="Error temporal del servicio.",
                content_type=content_type,
            )

        if response.status_code >= 400:
            return ProviderResult(
                success=False,
                status_code=response.status_code,
                message="La solicitud fue rechazada.",
                content_type=content_type,
            )

        if "application/json" in content_type:
            try:
                payload = response.json()
            except ValueError:
                return ProviderResult(
                    success=False,
                    status_code=502,
                    message="Respuesta JSON inválida.",
                    content_type=content_type,
                )

            no_results = self._detect_no_results(
                payload
            )

            return ProviderResult(
                success=True,
                status_code=response.status_code,
                data=payload,
                message=(
                    "Sin resultados."
                    if no_results
                    else "Consulta completada."
                ),
                no_results=no_results,
                content_type=content_type,
            )

        # Para PDF, imágenes u otros archivos.
        return ProviderResult(
            success=True,
            status_code=response.status_code,
            data=response.content,
            message="Archivo recibido.",
            no_results=False,
            content_type=content_type,
        )

    @staticmethod
    def _detect_no_results(
        payload: Any,
    ) -> bool:
        """
        Detecta respuestas vacías de manera genérica.

        Después se ajustará a la estructura exacta
        de la API oficial.
        """

        if payload is None:
            return True

        if payload == "":
            return True

        if payload == []:
            return True

        if payload == {}:
            return True

        if isinstance(payload, dict):
            for key in (
                "data",
                "results",
                "result",
            ):
                if key in payload and payload[key] in (
                    None,
                    "",
                    [],
                    {},
                ):
                    return True

        return False


fuentesdata_service = FuentesDataService()
