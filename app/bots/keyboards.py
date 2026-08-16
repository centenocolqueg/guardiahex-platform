from __future__ import annotations

from collections.abc import Iterable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.catalog import CATEGORY_META


# =========================================================
# CATEGORÍAS
# =========================================================

def _normalize_categories(
    categories: Iterable[str],
) -> list[str]:
    """
    Normaliza categorías y elimina cualquier valor
    que no exista en el catálogo maestro.
    """

    allowed: list[str] = []
    seen: set[str] = set()

    for category in categories:
        value = (
            str(category)
            .strip()
            .upper()
        )

        if not value:
            continue

        if value not in CATEGORY_META:
            continue

        if value in seen:
            continue

        seen.add(value)
        allowed.append(value)

    return allowed


# =========================================================
# MENÚ PRINCIPAL /cmds
# =========================================================

def build_categories_keyboard(
    enabled_categories: Iterable[str],
) -> InlineKeyboardMarkup:
    """
    Construye únicamente las categorías autorizadas
    para la versión actual del bot.

    Ejemplo:

    V1 -> 10 categorías
    V2 -> 13 categorías
    V3 -> 16 categorías
    V4 -> 18 categorías
    V5 -> 19 categorías

    No existe fallback automático a las 19 categorías.
    """

    builder = InlineKeyboardBuilder()

    categories = _normalize_categories(
        enabled_categories
    )

    for category in categories:

        meta = CATEGORY_META[
            category
        ]

        icon = str(
            meta.get(
                "icon",
                "📁",
            )
        )

        title = str(
            meta.get(
                "title",
                category,
            )
        )

        builder.button(
            text=(
                f"{icon} {title}"
            ),
            callback_data=(
                f"category:{category}:1"
            ),
        )

    # Máximo 2 categorías por fila.
    builder.adjust(2)

    return builder.as_markup()


# =========================================================
# NAVEGACIÓN DE CATEGORÍA
# =========================================================

def build_category_page_keyboard(
    *,
    category: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """
    Navegación segura dentro de una categoría.

    No decide si la categoría pertenece a V1-V5.
    Esa autorización se verifica previamente
    en callbacks.py.
    """

    builder = InlineKeyboardBuilder()

    category = (
        str(category)
        .strip()
        .upper()
    )

    page = max(
        1,
        int(page),
    )

    total_pages = max(
        1,
        int(total_pages),
    )

    # =====================================================
    # ANTERIOR
    # =====================================================

    if page > 1:
        builder.button(
            text="⬅️ ANTERIOR",
            callback_data=(
                f"category:"
                f"{category}:"
                f"{page - 1}"
            ),
        )

    # =====================================================
    # SIGUIENTE
    # =====================================================

    if page < total_pages:
        builder.button(
            text="SIGUIENTE ➡️",
            callback_data=(
                f"category:"
                f"{category}:"
                f"{page + 1}"
            ),
        )

    builder.adjust(2)

    # =====================================================
    # VOLVER
    # =====================================================

    builder.row(
        InlineKeyboardButton(
            text="🏠 REGRESAR AL MENÚ",
            callback_data=(
                "menu:categories"
            ),
        )
    )

    return builder.as_markup()


# =========================================================
# COMPRA / CONTACTO
# =========================================================

def build_buy_contacts_keyboard(
    founders: list[dict] | None = None,
    channel_url: str | None = None,
    group_url: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Botones oficiales de compra/contacto.

    Cada bot puede tener como máximo:
    - 4 FUNDADOR / COFUNDADOR
    - 1 canal
    - 1 grupo
    """

    builder = InlineKeyboardBuilder()

    founders = (
        founders or []
    )

    founder_buttons: list[
        InlineKeyboardButton
    ] = []

    for index, founder in enumerate(
        founders[:4],
        start=1,
    ):

        role = (
            str(
                founder.get(
                    "role",
                    "FUNDADOR",
                )
            )
            .strip()
            .upper()
        )

        url = (
            founder.get(
                "url"
            )
        )

        if not url:
            continue

        if role == "COFUNDADOR":
            icon = "🤝"
            title = "COFUNDADOR"

        else:
            icon = "👑"
            title = "FUNDADOR"

        founder_buttons.append(
            InlineKeyboardButton(
                text=(
                    f"{icon} "
                    f"{title} "
                    f"{index}"
                ),
                url=str(url),
            )
        )

    # Dos fundadores por fila.
    for index in range(
        0,
        len(founder_buttons),
        2,
    ):
        builder.row(
            *founder_buttons[
                index:index + 2
            ]
        )

    # =====================================================
    # CANAL
    # =====================================================

    if channel_url:
        builder.row(
            InlineKeyboardButton(
                text="📢 CANAL OFICIAL",
                url=str(
                    channel_url
                ),
            )
        )

    # =====================================================
    # GRUPO
    # =====================================================

    if group_url:
        builder.row(
            InlineKeyboardButton(
                text="👥 GRUPO OFICIAL",
                url=str(
                    group_url
                ),
            )
        )

    return builder.as_markup()


# =========================================================
# ESTADO DEL BOT
# =========================================================

def build_bot_status_keyboard(
    bot_id: int,
    enabled: bool,
) -> InlineKeyboardMarkup:
    """
    Acción rápida administrativa ON/OFF.

    La autorización real debe verificarse
    en el handler correspondiente.
    """

    builder = InlineKeyboardBuilder()

    if enabled:

        builder.button(
            text="🔴 APAGAR BOT",
            callback_data=(
                f"bot:disable:{int(bot_id)}"
            ),
        )

    else:

        builder.button(
            text="🟢 ENCENDER BOT",
            callback_data=(
                f"bot:enable:{int(bot_id)}"
            ),
        )

    builder.adjust(1)

    return builder.as_markup()


# =========================================================
# INFORMACIÓN
# =========================================================

def build_information_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text="ℹ️ INFORMACIÓN",
        callback_data="action:info",
    )

    builder.adjust(1)

    return builder.as_markup()
