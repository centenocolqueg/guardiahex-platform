from html import escape
from typing import Any


# =========================================================
# UTILIDADES
# =========================================================

def safe(value: Any) -> str:
    """
    Escapa texto para evitar romper el formato HTML
    utilizado por Telegram.
    """
    if value is None:
        return ""

    return escape(str(value))


def normalize_bot_name(
    bot_name: str | None,
) -> str:
    """
    Devuelve un nombre limpio para encabezados.
    """
    value = (bot_name or "GUARDIAHEXBOT").strip()

    if value.startswith("@"):
        value = value[1:]

    return value or "GUARDIAHEXBOT"


def format_credits(amount: int) -> str:
    """
    Formatea cantidades de créditos.
    """
    return f"{int(amount):,}".replace(",", ".")


def format_currency(
    amount: float | int,
) -> str:
    """
    Formato monetario peruano.
    """
    return f"S/ {float(amount):,.2f}"


def separator() -> str:
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


# =========================================================
# ENCABEZADOS
# =========================================================

def format_bot_header(
    bot_name: str,
    title: str,
    icon: str = "🔎",
) -> str:
    name = safe(
        normalize_bot_name(bot_name)
    )

    return (
        f"[#<b>{name}</b> {icon}] ➾ "
        f"<b>{safe(title)}</b>"
    )


# =========================================================
# ACCESO DENEGADO
# =========================================================

def format_access_denied() -> str:
    return (
        "[✖️] ¿Qué chucha quieres? "
        "No tienes permiso para hacer esto."
    )


# =========================================================
# PERFIL /me
# =========================================================

def format_profile(
    *,
    bot_name: str,
    username: str | None,
    telegram_id: int,
    role: str,
    plan: str,
    credits: int,
    status: str = "ACTIVO",
    expires_at: str | None = None,
) -> str:
    username_text = (
        f"@{username.lstrip('@')}"
        if username
        else "Sin username"
    )

    lines = [
        format_bot_header(
            bot_name,
            "ESTADO DE CUENTA",
            "👤",
        ),
        "",
        separator(),
        "",
        f"USUARIO ➾ <b>{safe(username_text)}</b>",
        f"ID ➾ <code>{telegram_id}</code>",
        f"ROL ➾ <b>{safe(role)}</b>",
        f"PLAN ➾ <b>{safe(plan)}</b>",
        (
            "CRÉDITOS ➾ "
            f"<b>{format_credits(credits)}</b>"
        ),
        f"ESTADO ➾ <b>{safe(status)}</b> ✅",
    ]

    if expires_at:
        lines.append(
            f"VENCE ➾ <b>{safe(expires_at)}</b>"
        )

    lines.extend(
        [
            "",
            separator(),
        ]
    )

    return "\n".join(lines)


# =========================================================
# RESULTADO DE CONSULTA AUTORIZADA
# =========================================================

def format_query_result(
    *,
    bot_name: str,
    service: str,
    level: str,
    result: str,
    cost: int,
    remaining_credits: int,
    username: str | None,
    telegram_id: int,
) -> str:
    """
    Formato estándar para resultados textuales.

    Los archivos, imágenes o PDFs se enviarán
    por separado antes de este resumen.
    """

    username_text = (
        f"@{username.lstrip('@')}"
        if username
        else "Sin username"
    )

    return "\n".join(
        [
            format_bot_header(
                bot_name,
                service,
            ),
            "",
            f"NIVEL ➾ <b>{safe(level)}</b>",
            "ESTADO ➾ OPERATIVO ✅",
            "",
            separator(),
            "",
            "<b>RESULTADO</b>",
            "",
            safe(result),
            "",
            separator(),
            "",
            "💳 <b>ESTADO DE CUENTA</b>",
            "",
            (
                "COSTO ➾ "
                f"<b>{format_credits(cost)} "
                f"{'Crédito' if cost == 1 else 'Créditos'}</b>"
            ),
            (
                "CRÉDITOS RESTANTES ➾ "
                f"<b>{format_credits(remaining_credits)}</b>"
            ),
            f"USUARIO ➾ <b>{safe(username_text)}</b>",
            f"ID ➾ <code>{telegram_id}</code>",
        ]
    )


# =========================================================
# CONSULTA SIN RESULTADOS
# =========================================================

def format_no_results(
    *,
    bot_name: str,
    service: str,
    cost: int,
    remaining_credits: int,
    username: str | None,
    telegram_id: int,
) -> str:
    """
    Se utiliza cuando una consulta válida llegó
    al servicio pero no encontró información.

    La política comercial puede descontar el
    crédito aunque el resultado esté vacío.
    """

    username_text = (
        f"@{username.lstrip('@')}"
        if username
        else "Sin username"
    )

    return "\n".join(
        [
            format_bot_header(
                bot_name,
                service,
            ),
            "",
            "⚠️ <b>SIN RESULTADOS</b>",
            "",
            (
                "Verifique los datos e intente "
                "nuevamente."
            ),
            "",
            separator(),
            "",
            "💳 <b>ESTADO DE CUENTA</b>",
            "",
            (
                "COSTO ➾ "
                f"<b>{format_credits(cost)} "
                f"{'Crédito' if cost == 1 else 'Créditos'}</b>"
            ),
            (
                "CRÉDITOS RESTANTES ➾ "
                f"<b>{format_credits(remaining_credits)}</b>"
            ),
            f"USUARIO ➾ <b>{safe(username_text)}</b>",
            f"ID ➾ <code>{telegram_id}</code>",
        ]
    )


# =========================================================
# FORMATO INVÁLIDO
# =========================================================

def format_invalid_input(
    *,
    command: str,
    example: str,
) -> str:
    """
    Se usa antes de ejecutar una consulta.
    Al no haberse realizado la petición,
    no debe descontarse crédito.
    """

    return "\n".join(
        [
            "⚠️ <b>FORMATO INCORRECTO</b>",
            "",
            (
                "COMANDO ➾ "
                f"<code>{safe(command)}</code>"
            ),
            "",
            "UTILIZA:",
            f"<code>{safe(example)}</code>",
            "",
            "No se realizó ningún descuento.",
        ]
    )


# =========================================================
# CRÉDITOS /cred
# =========================================================

def format_credit_transaction(
    *,
    bot_name: str,
    target_username: str | None,
    target_id: int,
    previous_balance: int,
    amount: int,
    final_balance: int,
    executor_username: str | None,
    executor_id: int,
    executor_role: str,
) -> str:
    target_text = (
        f"@{target_username.lstrip('@')}"
        if target_username
        else "Sin username"
    )

    executor_text = (
        f"@{executor_username.lstrip('@')}"
        if executor_username
        else "Sin username"
    )

    return "\n".join(
        [
            format_bot_header(
                bot_name,
                "MOVIMIENTO DE CRÉDITOS",
                "💳",
            ),
            "",
            separator(),
            "",
            f"USUARIO ➾ <b>{safe(target_text)}</b>",
            f"ID ➾ <code>{target_id}</code>",
            (
                "SALDO ANTERIOR ➾ "
                f"<b>{format_credits(previous_balance)}</b>"
            ),
            (
                "CRÉDITOS AÑADIDOS ➾ "
                f"<b>+{format_credits(amount)}</b>"
            ),
            (
                "SALDO FINAL ➾ "
                f"<b>{format_credits(final_balance)}</b>"
            ),
            "",
            separator(),
            "",
            "👤 <b>OPERACIÓN REALIZADA POR</b>",
            "",
            f"USUARIO ➾ <b>{safe(executor_text)}</b>",
            f"ID ➾ <code>{executor_id}</code>",
            f"ROL ➾ <b>{safe(executor_role)}</b>",
            "",
            "ESTADO ➾ COMPLETADO ✅",
        ]
    )


# =========================================================
# SUSCRIPCIÓN /sub
# =========================================================

def format_subscription_update(
    *,
    bot_name: str,
    target_username: str | None,
    target_id: int,
    plan: str,
    days_added: int,
    expires_at: str,
    executor_role: str,
) -> str:
    target_text = (
        f"@{target_username.lstrip('@')}"
        if target_username
        else "Sin username"
    )

    return "\n".join(
        [
            format_bot_header(
                bot_name,
                "SUSCRIPCIÓN ACTIVADA",
                "💎",
            ),
            "",
            separator(),
            "",
            f"USUARIO ➾ <b>{safe(target_text)}</b>",
            f"ID ➾ <code>{target_id}</code>",
            f"PLAN ➾ <b>{safe(plan)}</b>",
            f"DÍAS AÑADIDOS ➾ <b>{days_added}</b>",
            f"VENCE ➾ <b>{safe(expires_at)}</b>",
            "",
            f"OPERADOR ➾ <b>{safe(executor_role)}</b>",
            "ESTADO ➾ ACTIVADO ✅",
        ]
    )


# =========================================================
# SELLER
# =========================================================

def format_seller_transfer(
    *,
    seller_id: int,
    target_id: int,
    amount: int,
    seller_remaining: int,
    target_balance: int,
) -> str:
    return "\n".join(
        [
            "👑 <b>TRANSFERENCIA SELLER</b>",
            "",
            separator(),
            "",
            f"SELLER ID ➾ <code>{seller_id}</code>",
            f"DESTINO ID ➾ <code>{target_id}</code>",
            (
                "TRANSFERIDO ➾ "
                f"<b>{format_credits(amount)} Créditos</b>"
            ),
            "",
            (
                "SALDO SELLER ➾ "
                f"<b>{format_credits(seller_remaining)}</b>"
            ),
            (
                "SALDO DESTINO ➾ "
                f"<b>{format_credits(target_balance)}</b>"
            ),
            "",
            "ESTADO ➾ COMPLETADO ✅",
        ]
    )


# =========================================================
# ERRORES INTERNOS
# =========================================================

def format_service_unavailable() -> str:
    """
    Mensaje público neutral.

    Los detalles técnicos reales se registrarán
    únicamente en logs privados.
    """
    return "\n".join(
        [
            "⚠️ <b>SERVICIO TEMPORALMENTE NO DISPONIBLE</b>",
            "",
            (
                "No fue posible completar la operación "
                "en este momento."
            ),
            "",
            "Intente nuevamente más tarde.",
        ]
    )


# =========================================================
# HISTORIAL / AUDITORÍA
# =========================================================

def mask_argument(
    value: str | None,
) -> str:
    """
    Reduce exposición de información en logs.

    Ejemplo:
    12345678 -> ****5678
    """
    if not value:
        return "—"

    text = str(value).strip()

    if len(text) <= 4:
        return "*" * len(text)

    return (
        "*" * (len(text) - 4)
        + text[-4:]
    )


def format_audit_entry(
    *,
    bot_name: str,
    action: str,
    actor_id: int,
    actor_role: str,
    target_id: int | None = None,
    argument: str | None = None,
) -> str:
    lines = [
        "🛡️ <b>HISTORIAL DEL SISTEMA</b>",
        "",
        f"BOT ➾ <b>{safe(bot_name)}</b>",
        f"ACCIÓN ➾ <b>{safe(action)}</b>",
        f"ACTOR ID ➾ <code>{actor_id}</code>",
        f"ROL ➾ <b>{safe(actor_role)}</b>",
    ]

    if target_id is not None:
        lines.append(
            f"DESTINO ID ➾ <code>{target_id}</code>"
        )

    if argument:
        lines.append(
            "DATO ➾ "
            f"<code>{safe(mask_argument(argument))}</code>"
        )

    lines.append(
        "ESTADO ➾ REGISTRADO ✅"
    )

    return "\n".join(lines)
