from __future__ import annotations

from enum import StrEnum


# =========================================================
# ROLES DEL SISTEMA
# =========================================================

class Role(StrEnum):
    SUPERADMIN = "SUPERADMIN"
    OWNER = "OWNER"
    FOUNDER = "FUNDADOR"
    COFOUNDER = "COFUNDADOR"
    ADMIN = "ADMIN"
    SELLER = "SELLER"
    USER = "USER"


# =========================================================
# JERARQUÍA
# =========================================================

ROLE_LEVELS: dict[Role, int] = {
    Role.USER: 10,
    Role.SELLER: 20,
    Role.ADMIN: 30,
    Role.COFOUNDER: 40,
    Role.FOUNDER: 40,
    Role.OWNER: 50,
    Role.SUPERADMIN: 100,
}


# =========================================================
# GRUPOS DE ROLES
# =========================================================

ALL_ROLES = frozenset(
    {
        Role.USER,
        Role.SELLER,
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    }
)


STAFF_ROLES = frozenset(
    {
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    }
)


MANAGEMENT_ROLES = frozenset(
    {
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    }
)


# =========================================================
# PERMISOS
# =========================================================

PERMISSIONS: dict[str, frozenset[Role]] = {

    # -----------------------------------------------------
    # USUARIO GENERAL
    # -----------------------------------------------------

    "use_queries": ALL_ROLES,

    "view_me": ALL_ROLES,

    "view_commands": ALL_ROLES,

    "view_buy": ALL_ROLES,


    # -----------------------------------------------------
    # CRÉDITOS
    # -----------------------------------------------------

    # Puede ejecutar el flujo /cred.
    #
    # SELLER:
    # solamente transfiere desde su saldo.
    #
    # Los demás roles autorizados podrán tener
    # capacidades administrativas según el servicio.
    "use_cred": frozenset(
        {
            Role.SELLER,
            Role.ADMIN,
            Role.COFOUNDER,
            Role.FOUNDER,
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),

    # Transferencia de saldo existente.
    "transfer_credits": frozenset(
        {
            Role.SELLER,
            Role.ADMIN,
            Role.COFOUNDER,
            Role.FOUNDER,
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),

    # Crear/asignar créditos administrativos.
    #
    # SELLER queda expresamente fuera.
    "grant_credits": frozenset(
        {
            Role.ADMIN,
            Role.COFOUNDER,
            Role.FOUNDER,
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),


    # -----------------------------------------------------
    # SELLERS
    # -----------------------------------------------------

    "manage_sellers": MANAGEMENT_ROLES,


    # -----------------------------------------------------
    # SUSCRIPCIONES
    # -----------------------------------------------------

    "manage_subscriptions": frozenset(
        {
            Role.ADMIN,
            Role.COFOUNDER,
            Role.FOUNDER,
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),


    # -----------------------------------------------------
    # MODERACIÓN
    # -----------------------------------------------------

    "manage_bans": STAFF_ROLES,

    "send_announcements": STAFF_ROLES,

    "view_statistics": STAFF_ROLES,

    "view_staff": STAFF_ROLES,


    # -----------------------------------------------------
    # BOT PROPIO
    # -----------------------------------------------------

    "toggle_own_bot": frozenset(
        {
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),

    "manage_founders": frozenset(
        {
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),

    "manage_group_channel": frozenset(
        {
            Role.OWNER,
            Role.SUPERADMIN,
        }
    ),


    # -----------------------------------------------------
    # SOLO SUPERADMIN
    # -----------------------------------------------------

    "manage_version": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),

    "manage_commands": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),

    "manage_provider_api": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),

    "manage_partners": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),

    "manage_bots": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),

    "view_global_statistics": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),

    "view_global_audit": frozenset(
        {
            Role.SUPERADMIN,
        }
    ),
}


# =========================================================
# NORMALIZAR ROL
# =========================================================

def normalize_role(
    role: str | Role,
) -> Role:
    """
    Convierte distintos nombres a un Role oficial.
    """

    if isinstance(role, Role):
        return role

    value = (
        str(role)
        .strip()
        .upper()
    )

    aliases: dict[str, Role] = {
        "SUPERADMIN": Role.SUPERADMIN,
        "SUPER_ADMIN": Role.SUPERADMIN,

        "OWNER": Role.OWNER,
        "DUEÑO": Role.OWNER,
        "DUENO": Role.OWNER,

        "FOUNDER": Role.FOUNDER,
        "FUNDADOR": Role.FOUNDER,

        "COFOUNDER": Role.COFOUNDER,
        "CO_FOUNDER": Role.COFOUNDER,
        "COFUNDADOR": Role.COFOUNDER,

        "ADMIN": Role.ADMIN,
        "ADMINISTRADOR": Role.ADMIN,

        "SELLER": Role.SELLER,
        "VENDEDOR": Role.SELLER,

        "USER": Role.USER,
        "USUARIO": Role.USER,
    }

    if value in aliases:
        return aliases[value]

    return Role(value)


# =========================================================
# PERMISO GENERAL
# =========================================================

def has_permission(
    role: str | Role,
    permission: str,
) -> bool:

    try:
        normalized_role = (
            normalize_role(role)
        )

    except ValueError:
        return False

    permission_name = (
        str(permission)
        .strip()
        .lower()
    )

    allowed_roles = (
        PERMISSIONS.get(
            permission_name
        )
    )

    if allowed_roles is None:
        return False

    return (
        normalized_role
        in allowed_roles
    )


# =========================================================
# NIVEL DE ROL
# =========================================================

def role_level(
    role: str | Role,
) -> int:

    try:
        normalized_role = (
            normalize_role(role)
        )

    except ValueError:
        return 0

    return ROLE_LEVELS.get(
        normalized_role,
        0,
    )


# =========================================================
# ADMINISTRAR OTRO ROL
# =========================================================

def can_manage_role(
    executor_role: str | Role,
    target_role: str | Role,
) -> bool:
    """
    Un rol no puede administrar a otro
    de igual o mayor jerarquía.

    SUPERADMIN puede administrar todos.
    """

    try:
        executor = normalize_role(
            executor_role
        )

        target = normalize_role(
            target_role
        )

    except ValueError:
        return False

    if executor == Role.SUPERADMIN:
        return True

    # Nadie fuera del SUPERADMIN puede
    # administrar al SUPERADMIN.
    if target == Role.SUPERADMIN:
        return False

    return (
        role_level(executor)
        > role_level(target)
    )


# =========================================================
# HELPERS DE CRÉDITOS
# =========================================================

def can_use_cred(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "use_cred",
    )


def can_transfer_credits(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "transfer_credits",
    )


def can_grant_credits(
    role: str | Role,
) -> bool:
    """
    SELLER siempre devuelve False.

    Esto deberá ser usado por el servicio de
    créditos para impedir que un SELLER genere
    saldo desde cero.
    """

    return has_permission(
        role,
        "grant_credits",
    )


def seller_transfer_only(
    role: str | Role,
) -> bool:

    try:
        return (
            normalize_role(role)
            == Role.SELLER
        )

    except ValueError:
        return False


# =========================================================
# HELPERS DE ADMINISTRACIÓN
# =========================================================

def can_manage_sellers(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "manage_sellers",
    )


def can_use_sub(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "manage_subscriptions",
    )


def can_view_statistics(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "view_statistics",
    )


def can_send_announcements(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "send_announcements",
    )


def can_manage_bans(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "manage_bans",
    )


def can_manage_commands(
    role: str | Role,
) -> bool:

    return has_permission(
        role,
        "manage_commands",
    )


# =========================================================
# STAFF
# =========================================================

def is_staff(
    role: str | Role,
) -> bool:

    try:
        normalized = normalize_role(
            role
        )

    except ValueError:
        return False

    return normalized in STAFF_ROLES


# =========================================================
# CMD + VERSIÓN
# =========================================================

def can_use_command_for_version(
    role: str | Role,
    *,
    version: str,
    command: str,
) -> bool:
    """
    Comprueba dos capas:

    1. El rol puede realizar consultas.
    2. La versión V1-V5 tiene habilitado el CMD.

    La comprobación final contra PostgreSQL y
    overrides del bot se realiza después.
    """

    if not has_permission(
        role,
        "use_queries",
    ):
        return False

    try:
        # Import local para evitar dependencias
        # circulares durante el inicio.
        from app.bots.catalog import (
            version_has_command,
        )

        return version_has_command(
            version,
            command,
        )

    except (
        ImportError,
        ValueError,
    ):
        return False
