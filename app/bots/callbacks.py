from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bots.catalog import (
    get_category_page,
    get_category_page_count,
)
from app.bots.keyboards import (
    build_categories_keyboard,
    build_category_page_keyboard,
)


def get_callbacks_router() -> Router:
    router = Router(name="guardiahex_callbacks")

    # =========================================================
    # ABRIR CATEGORÍA
    # callback:
    # category:RENIEC:1
    # =========================================================

    @router.callback_query(F.data.startswith("category:"))
    async def open_category(
        callback: CallbackQuery,
    ) -> None:
        if not callback.data:
            await callback.answer()
            return

        parts = callback.data.split(":")

        if len(parts) != 3:
            await callback.answer(
                "Opción inválida.",
                show_alert=True,
            )
            return

        category = parts[1].upper()

        try:
            page = int(parts[2])
        except ValueError:
            page = 1

        total_pages = get_category_page_count(category)

        if total_pages <= 0:
            await callback.answer(
                "Categoría no disponible.",
                show_alert=True,
            )
            return

        page = max(1, min(page, total_pages))

        text = get_category_page(
            category=category,
            page=page,
        )

        keyboard = build_category_page_keyboard(
            category=category,
            page=page,
            total_pages=total_pages,
        )

        if callback.message:
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                )
            except Exception:
                await callback.message.answer(
                    text,
                    reply_markup=keyboard,
                )

        await callback.answer()

    # =========================================================
    # VOLVER AL MENÚ DE CATEGORÍAS
    # =========================================================

    @router.callback_query(
        F.data == "menu:categories"
    )
    async def return_categories(
        callback: CallbackQuery,
    ) -> None:
        text = (
            "🔎 <b>SISTEMA DE COMANDOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Selecciona una categoría disponible "
            "según la versión del bot.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = build_categories_keyboard()

        if callback.message:
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                )
            except Exception:
                await callback.message.answer(
                    text,
                    reply_markup=keyboard,
                )

        await callback.answer()

    # =========================================================
    # BOTÓN DE INFORMACIÓN
    # =========================================================

    @router.callback_query(
        F.data == "action:info"
    )
    async def show_information(
        callback: CallbackQuery,
    ) -> None:
        await callback.answer(
            "GUARDIAHEXBOT PLATFORM",
            show_alert=True,
        )

    # =========================================================
    # CALLBACK DESCONOCIDO
    # =========================================================

    @router.callback_query()
    async def unknown_callback(
        callback: CallbackQuery,
    ) -> None:
        await callback.answer(
            "Esta opción no está disponible.",
        )

    return router
