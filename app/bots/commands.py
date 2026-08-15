from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message


def get_commands_router() -> Router:
    router = Router(name="guardiahex_commands")

    # =========================================================
    # /start
    # =========================================================

    @router.message(CommandStart())
    async def command_start(message: Message) -> None:
        user = message.from_user

        username = (
            f"@{user.username}"
            if user and user.username
            else "Usuario"
        )

        text = (
            "🛡️ <b>GUARDIAHEXBOT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Bienvenido, Ing. <b>{username}</b> 👋\n\n"
            "Has ingresado a nuestro sistema de servicios "
            "y herramientas disponibles desde Telegram.\n\n"
            "<b>COMANDOS PRINCIPALES:</b>\n\n"
            "/register ➾ Registra tu cuenta\n"
            "/cmds ➾ Lista de comandos\n"
            "/me ➾ Revisa tu perfil y actividad\n"
            "/buy ➾ Compra Créditos/Días\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👑 <b>ADMINISTRACIÓN OFICIAL</b>\n"
            "Información configurada por el bot.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Nota:</b>\n"
            "Antes de comprar, verifica que el vendedor "
            "se encuentre autorizado dentro del sistema."
        )

        await message.answer(text)

    # =========================================================
    # /register
    # =========================================================

    @router.message(Command("register"))
    async def command_register(message: Message) -> None:
        """
        Más adelante este comando consultará PostgreSQL.

        Si el usuario es nuevo:
        - crea cuenta;
        - asigna USER;
        - entrega 5 créditos una sola vez.

        Si ya existe:
        - no duplica cuenta;
        - no vuelve a entregar créditos.
        """

        user = message.from_user

        username = (
            f"@{user.username}"
            if user and user.username
            else "Usuario"
        )

        await message.answer(
            "✅ <b>REGISTRO</b>\n\n"
            f"Usuario ➾ <b>{username}</b>\n"
            f"Telegram ID ➾ <code>{user.id if user else 0}</code>\n\n"
            "El sistema de registro será conectado "
            "a la base de datos en los siguientes módulos."
        )

    # =========================================================
    # /cmds
    # =========================================================

    @router.message(Command("cmds"))
    async def command_cmds(message: Message) -> None:
        """
        El menú definitivo se generará dinámicamente según:

        V1 = 10 categorías / 25 CMD
        V2 = 13 categorías / 40 CMD
        V3 = 16 categorías / 55 CMD
        V4 = 18 categorías / 65 CMD
        V5 = 19 categorías / 72 CMD
        """

        text = (
            "🔎 <b>SISTEMA DE COMANDOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Selecciona una categoría desde el menú.\n\n"
            "🪪 RENIEC\n"
            "📞 TELEFONÍA\n"
            "⚖️ JUSTICIA\n"
            "🏛 SUNAT\n"
            "🏠 SUNARP\n"
            "🚗 VEHÍCULOS\n"
            "📜 CERTIFICADOS\n"
            "🎓 ESTUDIOS\n"
            "👥 FAMILIA\n"
            "💰 FINANCIERO\n"
            "🔎 SEEKER\n"
            "🚦 MTC\n"
            "📑 ACTAS\n"
            "💳 VOUCHER\n"
            "🛰 INTEL X\n"
            "💎 VIP\n"
            "🌎 INTERNACIONAL\n"
            "👑 SELLER\n"
            "📊 CONSULTAS MASIVAS\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "La versión del bot determinará qué "
            "categorías y CMD estarán habilitados."
        )

        await message.answer(text)

    # =========================================================
    # /me
    # =========================================================

    @router.message(Command("me"))
    async def command_me(message: Message) -> None:
        user = message.from_user

        username = (
            f"@{user.username}"
            if user and user.username
            else "Sin username"
        )

        text = (
            "👤 <b>MI CUENTA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"USUARIO ➾ <b>{username}</b>\n"
            f"ID ➾ <code>{user.id if user else 0}</code>\n"
            "ROL ➾ USER\n"
            "PLAN ➾ FREE\n"
            "CRÉDITOS ➾ Pendiente de sincronizar\n"
            "ESTADO ➾ ACTIVO ✅\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        await message.answer(text)

    # =========================================================
    # /buy
    # =========================================================

    @router.message(Command("buy"))
    async def command_buy(message: Message) -> None:
        text = (
            "✨ <b>PLANES Y TARIFAS EXCLUSIVAS</b> ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 <b>PLANES POR CRÉDITOS</b>\n\n"
            "🥈 <b>PROFESIONAL</b>\n"
            "• 150 + 50 Créditos ➾ S/ 15\n"
            "• 350 + 70 Créditos ➾ S/ 25\n"
            "• 550 + 150 Créditos ➾ S/ 45\n\n"
            "🥇 <b>BUSINESS</b>\n"
            "• 1500 + 300 Créditos ➾ S/ 90\n"
            "• 3500 + 500 Créditos ➾ S/ 150\n"
            "• 8500 + 500 Créditos ➾ S/ 300\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏆 <b>PLANES POR DÍAS</b>\n\n"
            "🎖 <b>PROFESIONAL</b>\n"
            "• 7 Días ➾ S/ 30\n"
            "• 15 Días ➾ S/ 50\n\n"
            "🎖 <b>PROFESIONAL PLUS</b>\n"
            "• 30 Días ➾ S/ 100\n"
            "• 60 Días ➾ S/ 150\n\n"
            "🎖 <b>BUSINESS</b>\n"
            "• 90 Días ➾ S/ 250\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💼 <b>ROL SELLER</b>\n"
            "• Permite transferir créditos desde "
            "el saldo propio del vendedor.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛒 <b>¡ADQUIERE TU PLAN!</b>"
        )

        await message.answer(text)

    # =========================================================
    # /estadisticas
    # =========================================================

    @router.message(Command("estadisticas"))
    async def command_statistics(message: Message) -> None:
        await message.answer(
            "📊 <b>ESTADÍSTICAS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Las estadísticas de este bot serán "
            "cargadas en tiempo real desde PostgreSQL.\n\n"
            "👥 Usuarios ➾ —\n"
            "🔎 Consultas hoy ➾ —\n"
            "💳 Créditos movidos ➾ —\n"
            "💎 Suscripciones ➾ —\n"
            "💼 Sellers ➾ —\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    # =========================================================
    # COMANDO DESCONOCIDO
    # =========================================================

    @router.message(F.text.startswith("/"))
    async def unknown_command(message: Message) -> None:
        await message.answer(
            "⚠️ <b>COMANDO NO RECONOCIDO</b>\n\n"
            "Usa /cmds para consultar los comandos "
            "disponibles en tu versión."
        )

    return router
