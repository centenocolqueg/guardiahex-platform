from collections.abc import Iterable

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# CATEGORÍAS MAESTRAS
# =========================================================

CATEGORY_BUTTONS: list[tuple[str, str]] = [
    ("🪪 RENIEC", "RENIEC"),
    ("📞 TELEFONÍA", "TELEFONIA"),
    ("⚖️ JUSTICIA", "JUSTICIA"),
    ("🏛 SUNAT", "SUNAT"),
    ("🏠 SUNARP", "SUNARP"),
    ("🚗 VEHÍCULOS", "VEHICULOS"),
    ("📜 CERTIFICADOS", "CERTIFICADOS"),
    ("🎓 ESTUDIOS", "ESTUDIOS"),
    ("👥 FAMILIA", "FAMILIA"),
    ("💰 FINANCIERO", "FINANCIERO"),
    ("🔎 SEEKER", "SEEKER"),
    ("🚦 MTC", "MTC"),
    ("📑 ACTAS", "ACTAS"),
    ("💳 VOUCHER", "VOUCHER"),
    ("🛰 INTEL X", "INTEL_X"),
    ("💎 VIP", "VIP"),
    ("🌎 INTERNACIONAL", "INTERNACIONAL"),
    ("👑 SELLER", "SELLER"),
    ("📊 CONSULTAS MASIVAS", "CONSULTAS_MASIVAS"),
]


# =========================================================
# MENÚ PRINCIPAL DE /cmds
# =========================================================

def build_categories_keyboard(
    enabled_categories: Iterable[str] | None = None,
) -> InlineKeyboardMarkup:
    """
    Construye los botones del menú /cmds.

    Si enabled_categories es None:
        muestra las 19 categorías.

    Posteriormente cada versión V1-V5 enviará
    únicamente sus categorías habilitadas.
    """

    builder = InlineKeyboardBuilder()

    allowed = None

    if enabled_categories is not None:
        allowed = {
            category.upper()
            for category in enabled_categories
        }

    for text, category in CATEGORY_BUTTONS:
        if allowed is not None and category not in allowed:
            continue

        builder.button(
            text=text,
            callback_data=f"category:{category}:1",
        )

    # Dos botones por fila.
    builder.adjust(2)

    return builder.as_markup()


# =========================================================
# NAVEGACIÓN POR PÁGINAS DE UNA CATEGORÍA
# =========================================================

def build_category_page_keyboard(
    category: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """
    Crea:

    ⬅️ Página anterior
    ➡️ Página siguiente
    🏠 Regresar al menú

    Los botones disponibles dependen de la
    página actual.
    """

    builder = InlineKeyboardBuilder()

    category = category.upper()

    navigation_buttons = 0

    if page > 1:
        builder.button(
            text="⬅️",
            callback_data=(
                f"category:{category}:{page - 1}"
            ),
        )
        navigation_buttons += 1

    if page < total_pages:
        builder.button(
            text="➡️",
            callback_data=(
                f"category:{category}:{page + 1}"
            ),
        )
        navigation_buttons += 1

    if navigation_buttons:
        builder.adjust(navigation_buttons)

    builder.row(
        *[
            _inline_button(
                text="🏠 REGRESAR AL MENÚ",
                callback_data="menu:categories",
            )
        ]
    )

    return builder.as_markup()


# =========================================================
# BOTONES DE COMPRA / CONTACTO
# =========================================================

def build_buy_contacts_keyboard(
    founders: list[dict] | None = None,
    channel_url: str | None = None,
    group_url: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Construye los botones que aparecerán debajo de /buy.

    founders:
    [
        {
            "role": "FUNDADOR",
            "url": "https://t.me/usuario"
        },
        ...
    ]

    Máximo esperado por bot:
    4 FUNDADORES / COFUNDADORES.
    """

    builder = InlineKeyboardBuilder()

    founders = founders or []

    for index, founder in enumerate(
        founders[:4],
        start=1,
    ):
        role = str(
            founder.get("role", "FUNDADOR")
        ).upper()

        url = founder.get("url")

        if not url:
            continue

        if role == "COFUNDADOR":
            icon = "🤝"
            title = "COFUNDADOR"
        else:
            icon = "👑"
            title = "FUNDADOR"

        builder.button(
            text=f"{icon} {title} {index}",
            url=url,
        )

    # Fundadores/cofundadores, máximo dos por fila.
    builder.adjust(2)

    if channel_url:
        builder.row(
            _inline_button(
                text="📢 CANAL",
                url=channel_url,
            )
        )

    if group_url:
        builder.row(
            _inline_button(
                text="👥 GRUPO",
                url=group_url,
            )
        )

    return builder.as_markup()


# =========================================================
# PANEL / ACCIONES RÁPIDAS DEL BOT
# =========================================================

def build_bot_status_keyboard(
    bot_id: int,
    enabled: bool,
) -> InlineKeyboardMarkup:
    """
    Botón ON/OFF utilizado por el panel o
    futuras acciones administrativas.
    """

    builder = InlineKeyboardBuilder()

    if enabled:
        builder.button(
            text="🔴 APAGAR BOT",
            callback_data=f"bot:disable:{bot_id}",
        )
    else:
        builder.button(
            text="🟢 ENCENDER BOT",
            callback_data=f"bot:enable:{bot_id}",
        )

    builder.adjust(1)

    return builder.as_markup()


# =========================================================
# UTILIDAD INTERNA
# =========================================================

def _inline_button(
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
):
    """
    Crea un InlineKeyboardButton sin repetir
    configuración en todo el archivo.
    """

    from aiogram.types import InlineKeyboardButton

    if url:
        return InlineKeyboardButton(
            text=text,
            url=url,
        )

    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
    )
