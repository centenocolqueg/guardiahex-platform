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
# PERMISOS PRINCIPALES
# =========================================================

PERMISSIONS: dict[str, set[Role]] = {
    # Consultas generales
    "use_queries": {
        Role.USER,
        Role.SELLER,
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Ver perfil
    "view_me": {
        Role.USER,
        Role.SELLER,
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Ver catálogo /cmds
    "view_commands": {
        Role.USER,
        Role.SELLER,
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Ver planes /buy
    "view_buy": {
        Role.USER,
        Role.SELLER,
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Añadir / transferir créditos
    "use_cred": {
        Role.SELLER,
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Crear/quitar seller
    "manage_sellers": {
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Suscripciones /sub
    "manage_subscriptions": {
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Ban / unban
    "manage_bans": {
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Anuncios
    "send_announcements": {
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Estadísticas del bot
    "view_statistics": {
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Ver staff
    "view_staff": {
        Role.ADMIN,
        Role.COFOUNDER,
        Role.FOUNDER,
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Encender/apagar bot propio
    "toggle_own_bot": {
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Gestionar fundadores/cofundadores
    "manage_founders": {
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Cambiar grupo/canal del bot propio
    "manage_group_channel": {
        Role.OWNER,
        Role.SUPERADMIN,
    },

    # Cambiar versión V1-V5
    "manage_version": {
        Role.SUPERADMIN,
    },

    # Activar/desactivar CMD
    "manage_commands": {
        Role.SUPERADMIN,
    },

    # Configurar API maestra
    "manage_provider_api": {
        Role.SUPERADMIN,
    },

    # Crear/eliminar socios
    "manage_partners": {
        Role.SUPERADMIN,
    },

    # Crear/eliminar bots
    "manage_bots": {
        Role.SUPERADMIN,
    },

    # Ver estadísticas globales
    "view_global_statistics": {
        Role.SUPERADMIN,
    },

    # Ver auditoría global
    "view_global_audit": {
        Role.SUPERADMIN,
    },
}


# =========================================================
# FUNCIONES DE PERMISOS
# =========================================================

def normalize_role(role: str | Role) -> Role:
    """
    Convierte texto a Role.

    Ejemplos:
    OWNER
    owner
    FUNDADOR
    COFUNDADOR
    SELLER
    """

    if isinstance(role, Role):
        return role

    value = str(role).strip().upper()

    aliases = {
        "FOUNDER": Role.FOUNDER,
        "FUNDADOR": Role.FOUNDER,
        "COFOUNDER": Role.COFOUNDER,
        "COFUNDADOR": Role.COFOUNDER,
        "SUPER_ADMIN": Role.SUPERADMIN,
        "SUPERADMIN": Role.SUPERADMIN,
    }

    if value in aliases:
        return aliases[value]

    return Role(value)


def has_permission(
    role: str | Role,
    permission: str,
) -> bool:
    """
    Indica si un rol posee un permiso.
    """

    try:
        normalized_role = normalize_role(role)
    except ValueError:
        return False

    allowed_roles = PERMISSIONS.get(permission)

    if not allowed_roles:
        return False

    return normalized_role in allowed_roles


def role_level(role: str | Role) -> int:
    """
    Devuelve el nivel jerárquico del rol.
    """

    try:
        normalized_role = normalize_role(role)
    except ValueError:
        return 0

    return ROLE_LEVELS.get(
        normalized_role,
        0,
    )


def can_manage_role(
    executor_role: str | Role,
    target_role: str | Role,
) -> bool:
    """
    Evita que un rol inferior administre
    a uno igual o superior.

    SUPERADMIN puede administrar todos.
    """

    try:
        executor = normalize_role(executor_role)
        target = normalize_role(target_role)
    except ValueError:
        return False

    if executor == Role.SUPERADMIN:
        return True

    return role_level(executor) > role_level(target)


def can_use_cred(
    role: str | Role,
) -> bool:
    return has_permission(
        role,
        "use_cred",
    )


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
