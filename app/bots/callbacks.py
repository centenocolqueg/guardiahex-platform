from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bots.catalog import (
    get_category_page,
    get_category_page_count,
    get_enabled_categories,
    normalize_version,
)
from app.bots.keyboards import (
    build_categories_keyboard,
    build_category_page_keyboard,
)


# =========================================================
# UTILIDADES
# =========================================================

def _safe_version(
    bot_version: str | None,
) -> str:
    """
    Valida la versión recibida desde middleware.

    Si existe una configuración inválida,
    usa V1 como modo seguro.
    """

    try:
        return normalize_version(
            bot_version or "V1"
        )

    except ValueError:
        return "V1"


def _category_allowed(
    *,
    category: str,
    version: str,
) -> bool:

    enabled_categories = (
        get_enabled_categories(
            version
        )
    )

    return (
        category.upper()
        in {
            item.upper()
            for item
            in enabled_categories
        }
    )


# =========================================================
# ROUTER
# =========================================================

def get_callbacks_router() -> Router:

    router = Router(
        name="guardiahex_callbacks"
    )

    # =====================================================
    # ABRIR / NAVEGAR CATEGORÍA
    #
    # category:RENIEC:1
    # =====================================================

    @router.callback_query(
        F.data.startswith(
            "category:"
        )
    )
    async def open_category(
        callback: CallbackQuery,
        bot_version: str,
    ) -> None:

        data = callback.data

        if not data:
            await callback.answer()
            return

        parts = data.split(
            ":",
            maxsplit=2,
        )

        if len(parts) != 3:

            await callback.answer(
                "Opción inválida.",
                show_alert=True,
            )

            return

        category = (
            parts[1]
            .strip()
            .upper()
        )

        version = (
            _safe_version(
                bot_version
            )
        )

        # =============================================
        # BLOQUEO POR VERSIÓN
        # =============================================

        if not _category_allowed(
            category=category,
            version=version,
        ):

            await callback.answer(
                "Esta categoría no está "
                "disponible en tu versión.",
                show_alert=True,
            )

            return

        # =============================================
        # PÁGINA
        # =============================================

        try:
            page = int(
                parts[2]
            )

        except (
            TypeError,
            ValueError,
        ):
            page = 1

        if page <= 0:
            page = 1

        try:
            total_pages = (
                get_category_page_count(
                    category,
                    version=version,
                )
            )

        except ValueError:

            await callback.answer(
                "Categoría no disponible.",
                show_alert=True,
            )

            return

        if total_pages <= 0:

            await callback.answer(
                "Esta categoría no contiene "
                "comandos disponibles.",
                show_alert=True,
            )

            return

        # Nunca permitimos navegar fuera
        # del rango autorizado.
        page = min(
            page,
            total_pages,
        )

        try:
            text = get_category_page(
                category=category,
                page=page,
                version=version,
            )

        except ValueError:

            await callback.answer(
                "No fue posible abrir "
                "esta categoría.",
                show_alert=True,
            )

            return

        keyboard = (
            build_category_page_keyboard(
                category=category,
                page=page,
                total_pages=total_pages,
            )
        )

        # =============================================
        # ACTUALIZAR MENSAJE
        # =============================================

        if callback.message:

            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                )

            except Exception:
                # Por ejemplo:
                # mensaje sin cambios,
                # mensaje antiguo,
                # edición no permitida.
                try:
                    await callback.message.answer(
                        text,
                        reply_markup=keyboard,
                    )

                except Exception:
                    pass

        await callback.answer()

    # =====================================================
    # VOLVER AL MENÚ /cmds
    # =====================================================

    @router.callback_query(
        F.data == "menu:categories"
    )
    async def return_categories(
        callback: CallbackQuery,
        bot_version: str,
    ) -> None:

        version = (
            _safe_version(
                bot_version
            )
        )

        enabled_categories = (
            get_enabled_categories(
                version
            )
        )

        text = (
            "🔎 <b>SISTEMA DE COMANDOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"VERSIÓN ➾ <b>{version}</b>\n\n"

            "Selecciona una categoría "
            "disponible para este bot.\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = (
            build_categories_keyboard(
                enabled_categories
            )
        )

        if callback.message:

            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                )

            except Exception:

                try:
                    await callback.message.answer(
                        text,
                        reply_markup=keyboard,
                    )

                except Exception:
                    pass

        await callback.answer()

    # =====================================================
    # INFORMACIÓN
    # =====================================================

    @router.callback_query(
        F.data == "action:info"
    )
    async def show_information(
        callback: CallbackQuery,
        bot_version: str,
    ) -> None:

        version = (
            _safe_version(
                bot_version
            )
        )

        await callback.answer(
            (
                "GUARDIAHEXBOT PLATFORM\n"
                f"Versión: {version}"
            ),
            show_alert=True,
        )

    # =====================================================
    # NOTA
    # =====================================================
    #
    # NO agregamos:
    #
    # @router.callback_query()
    #
    # porque un callback catch-all podría interceptar
    # acciones añadidas posteriormente por otros routers.
    # =====================================================

    return router
