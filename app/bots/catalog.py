from dataclasses import dataclass
from math import ceil


# =========================================================
# MODELO DE UN CMD
# =========================================================

@dataclass(frozen=True)
class CommandItem:
    category: str
    code: str
    command: str
    title: str
    level: str
    price: int
    result: str
    enabled: bool = True


# =========================================================
# CATEGORÍAS PRINCIPALES
# =========================================================

CATEGORY_ORDER: list[str] = [
    "RENIEC",
    "TELEFONIA",
    "JUSTICIA",
    "SUNAT",
    "SUNARP",
    "VEHICULOS",
    "CERTIFICADOS",
    "ESTUDIOS",
    "FAMILIA",
    "FINANCIERO",
    "SEEKER",
    "MTC",
    "ACTAS",
    "VOUCHER",
    "INTEL_X",
    "VIP",
    "INTERNACIONAL",
    "SELLER",
    "CONSULTAS_MASIVAS",
]


CATEGORY_META: dict[str, dict[str, str | int]] = {
    "RENIEC": {
        "title": "RENIEC",
        "icon": "🪪",
        "count": 9,
    },
    "TELEFONIA": {
        "title": "TELEFONÍA",
        "icon": "📞",
        "count": 5,
    },
    "JUSTICIA": {
        "title": "JUSTICIA",
        "icon": "⚖️",
        "count": 10,
    },
    "SUNAT": {
        "title": "SUNAT",
        "icon": "🏛",
        "count": 4,
    },
    "SUNARP": {
        "title": "SUNARP",
        "icon": "🏠",
        "count": 5,
    },
    "VEHICULOS": {
        "title": "VEHÍCULOS",
        "icon": "🚗",
        "count": 6,
    },
    "CERTIFICADOS": {
        "title": "CERTIFICADOS",
        "icon": "📜",
        "count": 3,
    },
    "ESTUDIOS": {
        "title": "ESTUDIOS",
        "icon": "🎓",
        "count": 2,
    },
    "FAMILIA": {
        "title": "FAMILIA",
        "icon": "👥",
        "count": 2,
    },
    "FINANCIERO": {
        "title": "FINANCIERO",
        "icon": "💰",
        "count": 4,
    },
    "SEEKER": {
        "title": "SEEKER",
        "icon": "🔎",
        "count": 2,
    },
    "MTC": {
        "title": "MTC",
        "icon": "🚦",
        "count": 5,
    },
    "ACTAS": {
        "title": "ACTAS",
        "icon": "📑",
        "count": 1,
    },
    "VOUCHER": {
        "title": "VOUCHER",
        "icon": "💳",
        "count": 2,
    },
    "INTEL_X": {
        "title": "INTEL X",
        "icon": "🛰",
        "count": 1,
    },
    "VIP": {
        "title": "VIP",
        "icon": "💎",
        "count": 2,
    },
    "INTERNACIONAL": {
        "title": "INTERNACIONAL",
        "icon": "🌎",
        "count": 1,
    },
    "SELLER": {
        "title": "SELLER",
        "icon": "👑",
        "count": 3,
    },
    "CONSULTAS_MASIVAS": {
        "title": "CONSULTAS MASIVAS",
        "icon": "📊",
        "count": 5,
    },
}


# =========================================================
# VERSIONES V1 - V5
# =========================================================

VERSION_CATEGORY_COUNTS: dict[str, int] = {
    "V1": 10,
    "V2": 13,
    "V3": 16,
    "V4": 18,
    "V5": 19,
}


VERSION_COMMAND_LIMITS: dict[str, int] = {
    "V1": 25,
    "V2": 40,
    "V3": 55,
    "V4": 65,
    "V5": 72,
}


# =========================================================
# CATÁLOGO BASE
# =========================================================

def _build_catalog() -> list[CommandItem]:
    """
    Construye los 72 espacios de CMD del sistema.

    Los nombres, precios, nivel y conexión real
    podrán modificarse posteriormente desde el
    panel maestro.

    No se colocan URLs ni credenciales del
    proveedor dentro del código.
    """

    catalog: list[CommandItem] = []

    for category in CATEGORY_ORDER:
        meta = CATEGORY_META[category]

        count = int(meta["count"])
        title = str(meta["title"])

        command_prefix = (
            category
            .lower()
            .replace("_", "")
        )

        for number in range(1, count + 1):
            code = f"{category}_{number:02d}"

            command = (
                f"/{command_prefix}{number}"
            )

            catalog.append(
                CommandItem(
                    category=category,
                    code=code,
                    command=command,
                    title=f"{title} - SERVICIO {number:02d}",
                    level="CONFIGURABLE",
                    price=1,
                    result=(
                        "RESULTADO AUTORIZADO SEGÚN "
                        "CONFIGURACIÓN DEL SERVICIO"
                    ),
                )
            )

    return catalog


COMMAND_CATALOG: list[CommandItem] = _build_catalog()


# =========================================================
# CONSULTAS DEL CATÁLOGO
# =========================================================

def get_all_commands() -> list[CommandItem]:
    return COMMAND_CATALOG.copy()


def get_category_commands(
    category: str,
) -> list[CommandItem]:
    category = category.upper()

    return [
        item
        for item in COMMAND_CATALOG
        if item.category == category
        and item.enabled
    ]


def get_command_by_name(
    command: str,
) -> CommandItem | None:
    normalized = command.strip().lower()

    for item in COMMAND_CATALOG:
        if item.command.lower() == normalized:
            return item

    return None


def get_command_by_code(
    code: str,
) -> CommandItem | None:
    normalized = code.strip().upper()

    for item in COMMAND_CATALOG:
        if item.code == normalized:
            return item

    return None


# =========================================================
# VERSIONES
# =========================================================

def normalize_version(
    version: str,
) -> str:
    value = version.strip().upper()

    if value not in VERSION_CATEGORY_COUNTS:
        return "V1"

    return value


def get_enabled_categories(
    version: str,
) -> list[str]:
    """
    V1 → primeras 10 categorías
    V2 → primeras 13
    V3 → primeras 16
    V4 → primeras 18
    V5 → las 19
    """

    version = normalize_version(version)

    amount = VERSION_CATEGORY_COUNTS[version]

    return CATEGORY_ORDER[:amount]


def get_version_command_limit(
    version: str,
) -> int:
    version = normalize_version(version)

    return VERSION_COMMAND_LIMITS[version]


def get_commands_for_version(
    version: str,
) -> list[CommandItem]:
    """
    Devuelve únicamente los CMD correspondientes
    a la versión seleccionada.
    """

    version = normalize_version(version)

    categories = set(
        get_enabled_categories(version)
    )

    command_limit = (
        VERSION_COMMAND_LIMITS[version]
    )

    available = [
        command
        for command in COMMAND_CATALOG
        if command.category in categories
        and command.enabled
    ]

    return available[:command_limit]


def version_has_category(
    version: str,
    category: str,
) -> bool:
    category = category.upper()

    return category in get_enabled_categories(
        version
    )


def version_has_command(
    version: str,
    command: str,
) -> bool:
    normalized = command.lower()

    return any(
        item.command.lower() == normalized
        for item in get_commands_for_version(version)
    )


# =========================================================
# PAGINACIÓN
# =========================================================

COMMANDS_PER_PAGE = 3


def get_category_page_count(
    category: str,
) -> int:
    commands = get_category_commands(category)

    if not commands:
        return 0

    return ceil(
        len(commands) / COMMANDS_PER_PAGE
    )


def get_category_page_commands(
    category: str,
    page: int,
) -> list[CommandItem]:
    commands = get_category_commands(category)

    if not commands:
        return []

    total_pages = get_category_page_count(
        category
    )

    page = max(
        1,
        min(page, total_pages),
    )

    start = (
        (page - 1)
        * COMMANDS_PER_PAGE
    )

    end = start + COMMANDS_PER_PAGE

    return commands[start:end]


# =========================================================
# FORMATO DE PÁGINA
# =========================================================

def get_category_page(
    category: str,
    page: int,
    bot_name: str = "GUARDIAHEXBOT",
) -> str:
    category = category.upper()

    meta = CATEGORY_META.get(category)

    if not meta:
        return (
            "⚠️ <b>CATEGORÍA NO DISPONIBLE</b>"
        )

    commands = get_category_page_commands(
        category,
        page,
    )

    total_pages = get_category_page_count(
        category
    )

    if not commands or total_pages == 0:
        return (
            "⚠️ <b>SIN COMANDOS DISPONIBLES</b>"
        )

    page = max(
        1,
        min(page, total_pages),
    )

    category_title = str(
        meta["title"]
    )

    icon = str(
        meta["icon"]
    )

    total_commands = len(
        get_category_commands(category)
    )

    lines: list[str] = [
        f"[#{bot_name} 🔎] ➾ "
        "<b>SISTEMA DE COMANDOS</b>",
        "",
        f"CATEGORÍA ➾ <b>{category_title}</b>",
        (
            f"COMANDOS ➾ "
            f"<b>{total_commands} disponibles</b>"
        ),
        (
            f"PÁGINA ➾ "
            f"<b>{page}/{total_pages}</b>"
        ),
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for item in commands:
        lines.extend(
            [
                "",
                (
                    f"{icon} "
                    f"<b>{item.title}</b>"
                ),
                "",
                "ESTADO ➾ OPERATIVO ✅",
                (
                    f"COMANDO ➾ "
                    f"<code>{item.command}</code>"
                ),
                (
                    f"NIVEL ➾ "
                    f"<b>{item.level}</b>"
                ),
                (
                    f"PRECIO ➾ "
                    f"<b>{item.price} Crédito</b>"
                    if item.price == 1
                    else (
                        f"PRECIO ➾ "
                        f"<b>{item.price} Créditos</b>"
                    )
                ),
                (
                    f"RESULTADO ➾ "
                    f"{item.result}"
                ),
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ]
        )

    return "\n".join(lines)


# =========================================================
# ESTADÍSTICAS DEL CATÁLOGO
# =========================================================

def total_categories() -> int:
    return len(CATEGORY_ORDER)


def total_commands() -> int:
    return len(COMMAND_CATALOG)


def catalog_summary() -> dict[str, int]:
    return {
        "categories": total_categories(),
        "commands": total_commands(),
        "v1_commands": VERSION_COMMAND_LIMITS["V1"],
        "v2_commands": VERSION_COMMAND_LIMITS["V2"],
        "v3_commands": VERSION_COMMAND_LIMITS["V3"],
        "v4_commands": VERSION_COMMAND_LIMITS["V4"],
        "v5_commands": VERSION_COMMAND_LIMITS["V5"],
    }
