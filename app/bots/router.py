from aiogram import Dispatcher, Router


def build_root_router() -> Router:
    """
    Construye el router principal utilizado por
    GUARDIAHEXBOT y todos los bots de socios.

    Todos comparten el mismo motor de funciones;
    la configuración de cada bot determina
    identidad, versión, permisos y CMD disponibles.
    """

    root_router = Router(
        name="guardiahex_root_router"
    )

    # Importaciones locales para evitar
    # dependencias circulares.
    from app.bots.commands import get_commands_router
    from app.bots.callbacks import get_callbacks_router

    commands_router = get_commands_router()
    callbacks_router = get_callbacks_router()

    root_router.include_router(commands_router)
    root_router.include_router(callbacks_router)

    return root_router


def attach_root_router(
    dispatcher: Dispatcher,
) -> Dispatcher:
    """
    Conecta el router central a un Dispatcher.

    Cada bot tendrá su propio Dispatcher,
    pero utilizará la misma estructura lógica.
    """

    root_router = build_root_router()

    dispatcher.include_router(root_router)

    return dispatcher
