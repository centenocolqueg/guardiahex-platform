"""
Modelos de base de datos de GUARDIAHEXBOT PLATFORM.

Cada bot de socio mantiene sus datos aislados
mediante relaciones con bot_id y socio_id.

Módulos:

- socio.py
    Cuentas de socios y acceso al panel.

- bot.py
    Configuración individual de cada bot.

- user.py
    Usuarios registrados dentro de cada bot.

- role.py
    Roles locales OWNER, FUNDADOR, COFUNDADOR,
    ADMIN, SELLER y USER.

- plan.py
    Versiones, planes y suscripciones.

- command.py
    Catálogo y configuración de comandos.

- transaction.py
    Movimientos de créditos y operaciones comerciales.

- audit.py
    Historial y auditoría del sistema.

- settings.py
    Configuraciones globales y particulares.
"""

__all__ = [
    "socio",
    "bot",
    "user",
    "role",
    "plan",
    "command",
    "transaction",
    "audit",
    "settings",
]
