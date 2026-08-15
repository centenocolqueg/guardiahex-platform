"""
Servicios internos de GUARDIAHEXBOT PLATFORM.

Esta capa contiene la lógica principal del sistema
separada de Telegram, FastAPI y la base de datos.

Módulos:

- fuentesdata.py
    Adaptador central para la API autorizada.

- credits.py
    Operaciones de créditos.

- sellers.py
    Gestión y transferencias de SELLER.

- subscriptions.py
    Planes y suscripciones por días.

- audit.py
    Registro de actividad y auditoría.

- bot_runtime.py
    Encendido, apagado y reinicio de bots.

- statistics.py
    Estadísticas globales y por bot.

- realtime.py
    Eventos y actualizaciones en tiempo real.

- pdf_reports.py
    Generación de reportes PDF autorizados.
"""

__all__ = [
    "fuentesdata",
    "credits",
    "sellers",
    "subscriptions",
    "audit",
    "bot_runtime",
    "statistics",
    "realtime",
    "pdf_reports",
]
