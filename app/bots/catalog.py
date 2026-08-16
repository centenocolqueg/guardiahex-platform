from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import ceil


# =========================================================
# CONSTANTES
# =========================================================

EXPECTED_TOTAL_CATEGORIES = 19
EXPECTED_TOTAL_COMMANDS = 72

COMMANDS_PER_PAGE = 3


# =========================================================
# MODELO CMD
# =========================================================

@dataclass(frozen=True, slots=True)
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
# CATEGORÍAS
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
# VERSIONES
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
# NORMALIZACIÓN
# =========================================================

def normalize_category(
    category: str,
) -> str:
    return (
        category
        .strip()
        .upper()
        .replace(" ", "_")
    )


def normalize_version(
    version: str,
) -> str:
    """
    Una versión inválida no debe convertirse
    silenciosamente en V1.
    """

    value = (
        version
        .strip()
        .upper()
    )

    if value not in VERSION_CATEGORY_COUNTS:
        raise ValueError(
            f"Versión inválida: {value!r}"
        )

    return value


# =========================================================
# CONSTRUIR CATÁLOGO
# =========================================================

def _build_catalog() -> list[CommandItem]:
    """
    Crea los 72 espacios lógicos del catálogo.

    Continúan siendo servicios genéricos.
    Los endpoints reales solo deberán configurarse
    cuando exista documentación autorizada.
    """

    catalog: list[CommandItem] = []

    for category in CATEGORY_ORDER:

        meta = CATEGORY_META[
            category
        ]

        count = int(
            meta["count"]
        )

        title = str(
            meta["title"]
        )

        prefix = (
            category
            .lower()
            .replace("_", "")
        )

        for number in range(
            1,
            count + 1,
        ):

            catalog.append(
                CommandItem(
                    category=category,

                    code=(
                        f"{category}_"
                        f"{number:02d}"
                    ),

                    command=(
                        f"/{prefix}"
                        f"{number}"
                    ),

                    title=(
                        f"{title} - "
                        f"SERVICIO {number:02d}"
                    ),

                    level="CONFIGURABLE",

                    price=1,

                    result=(
                        "RESULTADO AUTORIZADO "
                        "SEGÚN CONFIGURACIÓN "
                        "DEL SERVICIO"
                    ),

                    enabled=True,
                )
            )

    return catalog


COMMAND_CATALOG: list[
    CommandItem
] = _build_catalog()


# =========================================================
# VALIDACIÓN INTERNA
# =========================================================

def _validate_catalog() -> None:
    """
    Evita arrancar con un catálogo inconsistente.
    """

    if (
        len(CATEGORY_ORDER)
        != EXPECTED_TOTAL_CATEGORIES
    ):
        raise RuntimeError(
            "El catálogo debe contener "
            "exactamente 19 categorías."
        )

    if (
        len(COMMAND_CATALOG)
        != EXPECTED_TOTAL_COMMANDS
    ):
        raise RuntimeError(
            "El catálogo debe contener "
            "exactamente 72 CMD."
        )

    if (
        set(CATEGORY_ORDER)
        != set(CATEGORY_META)
    ):
        raise RuntimeError(
            "CATEGORY_ORDER y CATEGORY_META "
            "no coinciden."
        )

    codes = [
        item.code
        for item in COMMAND_CATALOG
    ]

    commands = [
        item.command
        for item in COMMAND_CATALOG
    ]

    if (
        len(codes)
        != len(set(codes))
    ):
        raise RuntimeError(
            "Existen códigos CMD duplicados."
        )

    if (
        len(commands)
        != len(set(commands))
    ):
        raise RuntimeError(
            "Existen comandos duplicados."
        )


_validate_catalog()


# =========================================================
# CATÁLOGO GENERAL
# =========================================================

def get_all_commands() -> list[CommandItem]:
    return list(
        COMMAND_CATALOG
    )


def get_command_by_name(
    command: str,
) -> CommandItem | None:

    normalized = (
        command
        .strip()
        .lower()
    )

    for item in COMMAND_CATALOG:

        if (
            item.command.lower()
            == normalized
        ):
            return item

    return None


def get_command_by_code(
    code: str,
) -> CommandItem | None:

    normalized = (
        code
        .strip()
        .upper()
    )

    for item in COMMAND_CATALOG:

        if (
            item.code
            == normalized
        ):
            return item

    return None


# =========================================================
# CATEGORÍAS POR VERSIÓN
# =========================================================

def get_enabled_categories(
    version: str,
) -> list[str]:

    version = normalize_version(
        version
    )

    amount = (
        VERSION_CATEGORY_COUNTS[
            version
        ]
    )

    return list(
        CATEGORY_ORDER[:amount]
    )


def version_has_category(
    version: str,
    category: str,
) -> bool:

    try:
        normalized_version = (
            normalize_version(
                version
            )
        )

    except ValueError:
        return False

    normalized_category = (
        normalize_category(
            category
        )
    )

    return (
        normalized_category
        in get_enabled_categories(
            normalized_version
        )
    )


# =========================================================
# REPARTO REAL DE CMD POR VERSIÓN
# =========================================================

@lru_cache(maxsize=5)
def _get_version_command_codes(
    version: str,
) -> tuple[str, ...]:
    """
    Reparte los CMD entre todas las categorías
    habilitadas.

    Ejemplo:
    V1 = 10 categorías + exactamente 25 CMD.

    No simplemente toma los primeros 25,
    porque eso dejaría categorías habilitadas
    sin ningún comando.
    """

    version = normalize_version(
        version
    )

    categories = (
        get_enabled_categories(
            version
        )
    )

    target = (
        VERSION_COMMAND_LIMITS[
            version
        ]
    )

    commands_by_category: dict[
        str,
        list[CommandItem],
    ] = {}

    for category in categories:

        commands_by_category[
            category
        ] = [
            item
            for item in COMMAND_CATALOG
            if (
                item.category
                == category
                and item.enabled
            )
        ]

    selected: list[str] = []

    position = 0

    while len(selected) < target:

        added = False

        for category in categories:

            commands = (
                commands_by_category[
                    category
                ]
            )

            if position >= len(
                commands
            ):
                continue

            selected.append(
                commands[position].code
            )

            added = True

            if (
                len(selected)
                >= target
            ):
                break

        if not added:
            break

        position += 1

    if len(selected) != target:
        raise RuntimeError(
            f"{version} debería tener "
            f"{target} CMD pero tiene "
            f"{len(selected)}."
        )

    return tuple(
        selected
    )


def get_version_command_limit(
    version: str,
) -> int:

    version = normalize_version(
        version
    )

    return (
        VERSION_COMMAND_LIMITS[
            version
        ]
    )


def get_commands_for_version(
    version: str,
) -> list[CommandItem]:

    try:
        version = normalize_version(
            version
        )

    except ValueError:
        return []

    allowed_codes = set(
        _get_version_command_codes(
            version
        )
    )

    # Conservamos el orden visual
    # original del catálogo.
    return [
        item
        for item in COMMAND_CATALOG
        if item.code in allowed_codes
    ]


def version_has_command(
    version: str,
    command: str,
) -> bool:

    normalized = (
        command
        .strip()
        .lower()
    )

    return any(
        item.command.lower()
        == normalized
        for item
        in get_commands_for_version(
            version
        )
    )


# =========================================================
# CMD POR CATEGORÍA
# =========================================================

def get_category_commands(
    category: str,
    version: str | None = None,
) -> list[CommandItem]:

    normalized_category = (
        normalize_category(
            category
        )
    )

    if version is None:

        return [
            item
            for item in COMMAND_CATALOG
            if (
                item.category
                == normalized_category
                and item.enabled
            )
        ]

    version_commands = (
        get_commands_for_version(
            version
        )
    )

    return [
        item
        for item in version_commands
        if (
            item.category
            == normalized_category
            and item.enabled
        )
    ]


# =========================================================
# PAGINACIÓN
# =========================================================

def get_category_page_count(
    category: str,
    version: str | None = None,
) -> int:

    commands = (
        get_category_commands(
            category,
            version,
        )
    )

    if not commands:
        return 0

    return ceil(
        len(commands)
        / COMMANDS_PER_PAGE
    )


def get_category_page_commands(
    category: str,
    page: int,
    version: str | None = None,
) -> list[CommandItem]:

    commands = (
        get_category_commands(
            category,
            version,
        )
    )

    if not commands:
        return []

    total_pages = (
        get_category_page_count(
            category,
            version,
        )
    )

    page = max(
        1,
        min(
            page,
            total_pages,
        ),
    )

    start = (
        (page - 1)
        * COMMANDS_PER_PAGE
    )

    end = (
        start
        + COMMANDS_PER_PAGE
    )

    return commands[
        start:end
    ]


# =========================================================
# FORMATO DE PÁGINA
# =========================================================

def get_category_page(
    category: str,
    page: int,
    bot_name: str = "GUARDIAHEXBOT",
    version: str | None = None,
) -> str:

    category = (
        normalize_category(
            category
        )
    )

    meta = CATEGORY_META.get(
        category
    )

    if meta is None:
        return (
            "⚠️ <b>CATEGORÍA "
            "NO DISPONIBLE</b>"
        )

    if (
        version is not None
        and not version_has_category(
            version,
            category,
        )
    ):
        return (
            "🔒 <b>CATEGORÍA NO DISPONIBLE "
            "EN ESTA VERSIÓN</b>"
        )

    commands = (
        get_category_page_commands(
            category,
            page,
            version,
        )
    )

    total_pages = (
        get_category_page_count(
            category,
            version,
        )
    )

    if (
        not commands
        or total_pages == 0
    ):
        return (
            "⚠️ <b>SIN COMANDOS "
            "DISPONIBLES</b>"
        )

    page = max(
        1,
        min(
            page,
            total_pages,
        ),
    )

    category_title = str(
        meta["title"]
    )

    icon = str(
        meta["icon"]
    )

    total_commands = len(
        get_category_commands(
            category,
            version,
        )
    )

    lines: list[str] = [
        (
            f"[#{bot_name} 🔎] ➾ "
            "<b>SISTEMA DE COMANDOS</b>"
        ),
        "",
        (
            f"CATEGORÍA ➾ "
            f"<b>{category_title}</b>"
        ),
        (
            f"COMANDOS ➾ "
            f"<b>{total_commands} "
            "disponibles</b>"
        ),
        (
            f"PÁGINA ➾ "
            f"<b>{page}/{total_pages}</b>"
        ),
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for item in commands:

        credit_text = (
            "Crédito"
            if item.price == 1
            else "Créditos"
        )

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
                    "COMANDO ➾ "
                    f"<code>{item.command}</code>"
                ),
                (
                    "NIVEL ➾ "
                    f"<b>{item.level}</b>"
                ),
                (
                    "PRECIO ➾ "
                    f"<b>{item.price} "
                    f"{credit_text}</b>"
                ),
                (
                    "RESULTADO ➾ "
                    f"{item.result}"
                ),
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ]
        )

    return "\n".join(
        lines
    )


# =========================================================
# ESTADÍSTICAS
# =========================================================

def total_categories() -> int:
    return len(
        CATEGORY_ORDER
    )


def total_commands() -> int:
    return len(
        COMMAND_CATALOG
    )


def catalog_summary() -> dict[str, int]:

    return {
        "categories": (
            total_categories()
        ),
        "commands": (
            total_commands()
        ),
        "v1_categories": 10,
        "v1_commands": 25,
        "v2_categories": 13,
        "v2_commands": 40,
        "v3_categories": 16,
        "v3_commands": 55,
        "v4_categories": 18,
        "v4_commands": 65,
        "v5_categories": 19,
        "v5_commands": 72,
    }
