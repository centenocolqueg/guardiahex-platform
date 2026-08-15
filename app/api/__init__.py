"""
API web de GUARDIAHEXBOT PLATFORM.

Contiene las rutas utilizadas por:

- Panel MASTER / SUPERADMIN.
- Panel de socios.
- Autenticación.
- Bots.
- Versiones.
- Comandos.
- Créditos.
- Estadísticas.
- Configuración del proveedor.
- WebSockets en tiempo real.

La autorización de cada ruta se controla
según el tipo de cuenta y el bot asociado.
"""

__all__ = [
    "auth",
    "dashboard",
    "socios",
    "bots",
    "versions",
    "commands",
    "credits",
    "statistics",
    "provider",
    "realtime",
]
