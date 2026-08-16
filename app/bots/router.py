from __future__ import annotations

from aiogram import Dispatcher, Router


def build_root_router() -> Router:
    """
    Router principal utilizado por:

    - GUARDIAHEXBOT MASTER
    - bots de socios

    Todos comparten el mismo motor.

    ORDEN IMPORTANTE:

    1. commands_router
       Comandos internos:
       /start
       /register
       /me
       /buy
       /cred
       /sub
       /seller
       /unseller
       /sellers
       /ban
       /unban
       /staff
       /estadisticas
       /anuncio

    2. callbacks_router
       Botones y navegación del catálogo.

    3. query_router
       Recibe los demás /CMD dinámicos
       disponibles en el catálogo.
    """

    root_router = Router(
        name="guardiahex_root_router"
    )

    # =====================================================
    # IMPORTACIONES LOCALES
    #
    # Evitan dependencias circulares.
    # =====================================================

    from app.bots.commands import (
        get_commands_router,
    )

    from app.bots.callbacks import (
        get_callbacks_router,
    )

    from app.bots.query_router import (
        get_query_router,
    )

    # =====================================================
    # CREAR ROUTERS
    # =====================================================

    commands_router = (
        get_commands_router()
    )

    callbacks_router = (
        get_callbacks_router()
    )

    query_router = (
        get_query_router()
    )

    # =====================================================
    # ORDEN DE PRIORIDAD
    # =====================================================

    # Primero:
    # comandos oficiales/administrativos.
    root_router.include_router(
        commands_router
    )

    # Segundo:
    # botones InlineKeyboard.
    root_router.include_router(
        callbacks_router
    )

    # Último:
    # receptor genérico de /CMD dinámicos.
    #
    # query_router contiene:
    #
    # F.text.startswith("/")
    #
    # por eso debe quedar después de
    # commands_router.
    root_router.include_router(
        query_router
    )

    return root_router


def attach_root_router(
    dispatcher: Dispatcher,
) -> Dispatcher:
    """
    Conecta el router principal al Dispatcher
    individual de cada bot.

    Cada bot tiene su propio Dispatcher,
    pero todos reutilizan la misma lógica.
    """

    root_router = (
        build_root_router()
    )

    dispatcher.include_router(
        root_router
    )

    return dispatcher
