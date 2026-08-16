from __future__ import annotations

from html import escape
from typing import Any


# =========================================================
# UTILIDADES
# =========================================================

def safe(
    value: Any,
) -> str:
    """
    Escapa cualquier contenido antes de enviarlo
    con parse_mode HTML a Telegram.
    """

    if value is None:
        return ""

    return escape(
        str(value),
        quote=True,
    )


def normalize_bot_name(
    bot_name: str | None,
) -> str:
    """
    Normaliza el nombre mostrado en respuestas.
    """

    value = (
        bot_name
        or "GUARDIAHEXBOT"
    )

    value = (
        str(value)
        .strip()
    )

    if value.startswith("@"):
        value = value[1:]

    return (
        value
        or "GUARDIAHEXBOT"
    )


def normalize_username(
    username: str | None,
) -> str:
    if not username:
        return "Sin username"

    value = (
        str(username)
        .strip()
        .lstrip("@")
    )

    if not value:
        return "Sin username"

    return f"@{value}"


def format_credits(
    amount: int | float,
) -> str:
    """
    Formato visual para créditos.

    1000 -> 1.000
    """

    try:
        number = int(
            amount
        )

    except (
        TypeError,
        ValueError,
    ):
        number = 0

    return (
        f"{number:,}"
        .replace(",", ".")
    )


def format_currency(
    amount: float | int,
) -> str:
    """
    Formato monetario peruano.
    """

    try:
        value = float(
            amount
        )

    except (
        TypeError,
        ValueError,
    ):
        value = 0.0

    return f"S/ {value:,.2f}"


def separator() -> str:
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


# =========================================================
# ENCABEZADO
# =========================================================

def format_bot_header(
    bot_name: str,
    title: str,
    icon: str = "🔎",
) -> str:

    name = safe(
        normalize_bot_name(
            bot_name
        )
    )

    return (
        f"[#<b>{name}</b> {safe(icon)}] ➾ "
        f"<b>{safe(title)}</b>"
    )


# =========================================================
# ACCESO DENEGADO
# =========================================================

def format_access_denied() -> str:
    return "\n".join(
        [
            "⛔ <b>ACCESO DENEGADO</b>",
            "",
            (
                "No tienes permisos para "
                "realizar esta operación."
            ),
        ]
    )


# =========================================================
# CUENTA NO REGISTRADA
# =========================================================

def format_account_required() -> str:
    return "\n".join(
        [
            "👤 <b>CUENTA NO REGISTRADA</b>",
            "",
            (
                "Utiliza /register para "
                "crear tu cuenta."
            ),
        ]
    )


# =========================================================
# CUENTA BLOQUEADA
# =========================================================

def format_account_blocked() -> str:
    return "\n".join(
        [
            "⛔ <b>CUENTA BLOQUEADA</b>",
            "",
            (
                "Tu cuenta no se encuentra "
                "habilitada para realizar "
                "esta operación."
            ),
        ]
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
        normalize_username(
            username
        )
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
        (
            "USUARIO ➾ "
            f"<b>{safe(username_text)}</b>"
        ),
        (
            "ID ➾ "
            f"<code>{int(telegram_id)}</code>"
        ),
        (
            "ROL ➾ "
            f"<b>{safe(role)}</b>"
        ),
        (
            "PLAN ➾ "
            f"<b>{safe(plan)}</b>"
        ),
        (
            "CRÉDITOS ➾ "
            f"<b>{format_credits(credits)}</b>"
        ),
        (
            "ESTADO ➾ "
            f"<b>{safe(status)}</b>"
        ),
    ]

    if expires_at:
        lines.append(
            "VENCE ➾ "
            f"<b>{safe(expires_at)}</b>"
        )

    lines.extend(
        [
            "",
            separator(),
        ]
    )

    return "\n".join(
        lines
    )


# =========================================================
# RESULTADO DE CONSULTA
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
    Resumen textual estándar.

    Si existe PDF/archivo, debe enviarse primero
    y este mensaje después.
    """

    username_text = (
        normalize_username(
            username
        )
    )

    return "\n".join(
        [
            format_bot_header(
                bot_name,
                service,
            ),
            "",
            (
                "NIVEL ➾ "
                f"<b>{safe(level)}</b>"
            ),
            (
                "ESTADO ➾ "
                "<b>COMPLETADO ✅</b>"
            ),
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
                f"{'Crédito' if int(cost) == 1 else 'Créditos'}</b>"
            ),
            (
                "CRÉDITOS RESTANTES ➾ "
                f"<b>{format_credits(remaining_credits)}</b>"
            ),
            (
                "USUARIO ➾ "
                f"<b>{safe(username_text)}</b>"
            ),
            (
                "ID ➾ "
                f"<code>{int(telegram_id)}</code>"
            ),
        ]
    )


# =========================================================
# SIN RESULTADOS
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
    Se usa únicamente cuando:

    - el formato de entrada fue válido;
    - la consulta realmente llegó al proveedor;
    - el proveedor respondió correctamente;
    - pero no encontró información.

    Esta operación puede consumir créditos.
    """

    username_text = (
        normalize_username(
            username
        )
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
                "Sin Resultados. Verifique los datos "
                "e intente nuevamente."
            ),
            "",
            separator(),
            "",
            "💳 <b>ESTADO DE CUENTA</b>",
            "",
            (
                "COSTO ➾ "
                f"<b>{format_credits(cost)} "
                f"{'Crédito' if int(cost) == 1 else 'Créditos'}</b>"
            ),
            (
                "CRÉDITOS RESTANTES ➾ "
                f"<b>{format_credits(remaining_credits)}</b>"
            ),
            (
                "USUARIO ➾ "
                f"<b>{safe(username_text)}</b>"
            ),
            (
                "ID ➾ "
                f"<code>{int(telegram_id)}</code>"
            ),
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
    Entrada inválida antes de llamar al proveedor.

    Nunca debe descontar créditos.
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
            "<b>UTILIZA:</b>",
            (
                f"<code>{safe(example)}</code>"
            ),
            "",
            (
                "💳 No se realizó "
                "ningún descuento."
            ),
        ]
    )


# =========================================================
# CRÉDITOS INSUFICIENTES
# =========================================================

def format_insufficient_credits(
    *,
    required: int,
    available: int,
) -> str:

    return "\n".join(
        [
            "💳 <b>CRÉDITOS INSUFICIENTES</b>",
            "",
            (
                "COSTO ➾ "
                f"<b>{format_credits(required)}</b>"
            ),
            (
                "SALDO ➾ "
                f"<b>{format_credits(available)}</b>"
            ),
            "",
            (
                "Utiliza /buy para consultar "
                "las opciones disponibles."
            ),
        ]
    )


# =========================================================
# TRANSACCIÓN /cred
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
        normalize_username(
            target_username
        )
    )

    executor_text = (
        normalize_username(
            executor_username
        )
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
            (
                "USUARIO ➾ "
                f"<b>{safe(target_text)}</b>"
            ),
            (
                "ID ➾ "
                f"<code>{int(target_id)}</code>"
            ),
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
            (
                "USUARIO ➾ "
                f"<b>{safe(executor_text)}</b>"
            ),
            (
                "ID ➾ "
                f"<code>{int(executor_id)}</code>"
            ),
            (
                "ROL ➾ "
                f"<b>{safe(executor_role)}</b>"
            ),
            "",
            "ESTADO ➾ <b>COMPLETADO ✅</b>",
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
        normalize_username(
            target_username
        )
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
            (
                "USUARIO ➾ "
                f"<b>{safe(target_text)}</b>"
            ),
            (
                "ID ➾ "
                f"<code>{int(target_id)}</code>"
            ),
            (
                "PLAN ➾ "
                f"<b>{safe(plan)}</b>"
            ),
            (
                "DÍAS AÑADIDOS ➾ "
                f"<b>{int(days_added)}</b>"
            ),
            (
                "VENCE ➾ "
                f"<b>{safe(expires_at)}</b>"
            ),
            "",
            (
                "OPERADOR ➾ "
                f"<b>{safe(executor_role)}</b>"
            ),
            (
                "ESTADO ➾ "
                "<b>ACTIVADO ✅</b>"
            ),
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
            (
                "SELLER ID ➾ "
                f"<code>{int(seller_id)}</code>"
            ),
            (
                "DESTINO ID ➾ "
                f"<code>{int(target_id)}</code>"
            ),
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
            (
                "ESTADO ➾ "
                "<b>COMPLETADO ✅</b>"
            ),
        ]
    )


# =========================================================
# SERVICIO NO DISPONIBLE
# =========================================================

def format_service_unavailable() -> str:
    """
    Nunca expone detalles internos,
    URLs, tokens ni errores del proveedor.
    """

    return "\n".join(
        [
            "⚠️ <b>SERVICIO TEMPORALMENTE NO DISPONIBLE</b>",
            "",
            (
                "No fue posible completar "
                "la operación en este momento."
            ),
            "",
            (
                "Intente nuevamente más tarde."
            ),
        ]
    )


# =========================================================
# CONSULTA NO DISPONIBLE POR VERSIÓN
# =========================================================

def format_command_not_available() -> str:

    return "\n".join(
        [
            "🔒 <b>CMD NO DISPONIBLE</b>",
            "",
            (
                "Este comando no se encuentra "
                "habilitado para la versión "
                "actual del bot."
            ),
        ]
    )


# =========================================================
# AUDITORÍA
# =========================================================

def mask_argument(
    value: str | None,
) -> str:
    """
    Minimiza exposición en logs.

    12345678 -> ****5678
    """

    if not value:
        return "—"

    text = (
        str(value)
        .strip()
    )

    if len(text) <= 4:
        return (
            "*" * len(text)
        )

    return (
        "*" * (
            len(text) - 4
        )
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
        (
            "BOT ➾ "
            f"<b>{safe(bot_name)}</b>"
        ),
        (
            "ACCIÓN ➾ "
            f"<b>{safe(action)}</b>"
        ),
        (
            "ACTOR ID ➾ "
            f"<code>{int(actor_id)}</code>"
        ),
        (
            "ROL ➾ "
            f"<b>{safe(actor_role)}</b>"
        ),
    ]

    if target_id is not None:
        lines.append(
            "DESTINO ID ➾ "
            f"<code>{int(target_id)}</code>"
        )

    if argument:
        lines.append(
            "DATO ➾ "
            f"<code>"
            f"{safe(mask_argument(argument))}"
            f"</code>"
        )

    lines.append(
        "ESTADO ➾ "
        "<b>REGISTRADO ✅</b>"
    )

    return "\n".join(
        lines
    )
