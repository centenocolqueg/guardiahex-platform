from __future__ import annotations

import json
import re
from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    Message,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.formatters import (
    format_access_denied,
    format_account_blocked,
    format_account_required,
    format_command_not_available,
    format_invalid_input,
    format_no_results,
    format_query_result,
    format_service_unavailable,
)
from app.bots.permissions import (
    Role,
    normalize_role,
    role_level,
)
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.bot import BotModel
from app.models.role import RoleModel
from app.models.user import UserModel
from app.services.credits import (
    InsufficientCreditsError,
)
from app.services.query_engine import (
    QueryAccountBlockedError,
    QueryAccountRequiredError,
    QueryBotUnavailableError,
    QueryCommandDisabledError,
    QueryCommandNotFoundError,
    QueryDailyLimitError,
    QueryEngineError,
    QueryInvalidInputError,
    QueryPermissionError,
    QueryProviderError,
    QueryProviderNotConfiguredError,
    query_engine,
)


# =========================================================
# SUPERADMIN
# =========================================================

def _superadmin_telegram_id() -> int | None:
    value = getattr(
        settings,
        "superadmin_telegram_id",
        None,
    )

    if value in (
        None,
        "",
        0,
        "0",
    ):
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _is_superadmin(
    *,
    telegram_id: int,
    is_master_bot: bool,
) -> bool:

    configured = (
        _superadmin_telegram_id()
    )

    return bool(
        is_master_bot
        and configured is not None
        and telegram_id == configured
    )


# =========================================================
# NORMALIZAR CMD
# =========================================================

def _normalize_command(
    text: str,
) -> tuple[str, str]:
    """
    Ejemplo:

    /cmd DATO

    Retorna:

    command = /cmd
    argument = DATO

    También soporta comandos enviados en grupos:

    /cmd@NombreBot DATO
    """

    value = (
        str(text or "")
        .strip()
    )

    parts = value.split(
        maxsplit=1
    )

    if not parts:
        return "", ""

    command = (
        parts[0]
        .strip()
        .lower()
    )

    # =====================================================
    # QUITAR @BOTNAME
    # =====================================================

    if "@" in command:
        command = (
            command
            .split(
                "@",
                maxsplit=1,
            )[0]
        )

    argument = (
        parts[1].strip()
        if len(parts) == 2
        else ""
    )

    return (
        command,
        argument,
    )


# =========================================================
# NOMBRE SEGURO DE ARCHIVO
# =========================================================

def _safe_filename(
    command: str,
    extension: str,
) -> str:

    name = (
        command
        .lstrip("/")
        .strip()
        .lower()
    )

    name = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        name,
    )

    if not name:
        name = "resultado"

    extension = (
        str(extension)
        .strip()
        .lower()
        .lstrip(".")
    )

    if not extension:
        extension = "bin"

    return (
        f"{name}.{extension}"
    )


# =========================================================
# BUSCAR USUARIO
# =========================================================

async def _get_user(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
) -> UserModel | None:

    result = await session.execute(
        select(
            UserModel
        ).where(
            UserModel.bot_id == bot_id,
            UserModel.telegram_id
            == telegram_id,
        )
    )

    return (
        result.scalar_one_or_none()
    )


# =========================================================
# ROL EFECTIVO
# =========================================================

async def _get_actor_role(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
    is_master_bot: bool,
) -> str:
    """
    SUPERADMIN se resuelve desde .env únicamente
    en el bot MASTER.

    Para los demás usuarios se obtiene el rol
    activo de mayor jerarquía dentro del bot.
    """

    if _is_superadmin(
        telegram_id=telegram_id,
        is_master_bot=is_master_bot,
    ):
        return "SUPERADMIN"

    user = await _get_user(
        session,
        bot_id=bot_id,
        telegram_id=telegram_id,
    )

    if user is None:
        return "USER"

    result = await session.execute(
        select(
            RoleModel.role
        ).where(
            RoleModel.bot_id == bot_id,
            RoleModel.user_id == user.id,
            RoleModel.is_active.is_(True),
        )
    )

    roles = list(
        result.scalars().all()
    )

    best_role = Role.USER

    best_level = role_level(
        Role.USER
    )

    for role_value in roles:

        try:
            normalized = normalize_role(
                str(role_value)
            )

        except ValueError:
            continue

        current_level = role_level(
            normalized
        )

        if current_level > best_level:

            best_role = normalized
            best_level = current_level

    return best_role.value


# =========================================================
# IDENTIDAD DEL BOT
# =========================================================

async def _get_bot_name(
    session: AsyncSession,
    *,
    bot_id: int,
) -> str:

    result = await session.execute(
        select(
            BotModel
        ).where(
            BotModel.id == bot_id
        )
    )

    bot = (
        result.scalar_one_or_none()
    )

    if bot is None:
        return "GUARDIAHEXBOT"

    if bot.username:
        return str(
            bot.username
        )

    if bot.display_name:
        return str(
            bot.display_name
        )

    return "GUARDIAHEXBOT"


# =========================================================
# SERIALIZAR RESPUESTA
# =========================================================

def _serialize_result(
    data: Any,
) -> str:

    if data is None:
        return ""

    if isinstance(
        data,
        str,
    ):
        return data

    if isinstance(
        data,
        (
            dict,
            list,
            tuple,
        ),
    ):

        try:
            return json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        except Exception:
            return str(data)

    return str(data)


# =========================================================
# ENVIAR RESULTADO BINARIO
# =========================================================

async def _send_binary_result(
    message: Message,
    *,
    command: str,
    content: bytes,
    content_type: str | None,
) -> None:
    """
    Archivos primero.

    Después query_router envía el resumen
    del estado de cuenta.
    """

    mime = (
        str(
            content_type
            or ""
        )
        .split(";")[0]
        .strip()
        .lower()
    )

    # =====================================================
    # PDF
    # =====================================================

    if mime == "application/pdf":

        file = BufferedInputFile(
            content,
            filename=_safe_filename(
                command,
                "pdf",
            ),
        )

        await message.answer_document(
            file
        )

        return

    # =====================================================
    # IMAGEN
    # =====================================================

    if mime in {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }:

        extension_map = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }

        extension = (
            extension_map.get(
                mime,
                "jpg",
            )
        )

        file = BufferedInputFile(
            content,
            filename=_safe_filename(
                command,
                extension,
            ),
        )

        try:
            await message.answer_photo(
                file
            )

        except Exception:

            fallback_file = (
                BufferedInputFile(
                    content,
                    filename=_safe_filename(
                        command,
                        extension,
                    ),
                )
            )

            await message.answer_document(
                fallback_file
            )

        return

    # =====================================================
    # OTROS ARCHIVOS
    # =====================================================

    extension = "bin"

    if mime == "application/json":
        extension = "json"

    elif mime == "text/plain":
        extension = "txt"

    elif mime == "text/csv":
        extension = "csv"

    elif mime in {
        "application/zip",
        "application/x-zip-compressed",
    }:
        extension = "zip"

    file = BufferedInputFile(
        content,
        filename=_safe_filename(
            command,
            extension,
        ),
    )

    await message.answer_document(
        file
    )


# =========================================================
# TEXTO / JSON EXTENSO
# =========================================================

async def _prepare_text_result(
    message: Message,
    *,
    command: str,
    data: Any,
) -> str:
    """
    Si la respuesta es pequeña se incluye
    directamente en Telegram.

    Si es grande se envía primero como archivo.
    """

    text = _serialize_result(
        data
    )

    if not text:
        return "Consulta completada."

    # Dejamos margen respecto al límite
    # máximo de Telegram.
    if len(text) <= 2500:
        return text

    content = (
        text.encode(
            "utf-8"
        )
    )

    extension = (
        "json"
        if isinstance(
            data,
            (
                dict,
                list,
                tuple,
            ),
        )
        else "txt"
    )

    file = BufferedInputFile(
        content,
        filename=_safe_filename(
            command,
            extension,
        ),
    )

    await message.answer_document(
        file
    )

    return (
        "Resultado completo enviado "
        "como archivo."
    )


# =========================================================
# ROUTER DE CONSULTAS
# =========================================================

def get_query_router() -> Router:

    router = Router(
        name="guardiahex_query_router"
    )

    # =====================================================
    # CMD DINÁMICOS
    #
    # IMPORTANTE:
    #
    # Este router debe incluirse DESPUÉS
    # de commands_router.
    #
    # Así /start /register /cred /sub /seller...
    # son procesados antes.
    # =====================================================

    @router.message(
        F.text.startswith("/")
    )
    async def dynamic_query(
        message: Message,
        internal_bot_id: int,
        bot_version: str,
        is_master_bot: bool,
        request_id: str | None = None,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        text = (
            message.text
            or ""
        )

        command, argument = (
            _normalize_command(
                text
            )
        )

        if not command:

            await message.answer(
                "⚠️ <b>COMANDO INVÁLIDO</b>"
            )

            return

        async with AsyncSessionLocal() as session:

            try:

                # =========================================
                # ROL
                # =========================================

                role = (
                    await _get_actor_role(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),

                        telegram_id=(
                            tg_user.id
                        ),

                        is_master_bot=(
                            is_master_bot
                        ),
                    )
                )

                # =========================================
                # NOMBRE DEL BOT
                # =========================================

                bot_name = (
                    await _get_bot_name(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),
                    )
                )

                # =========================================
                # MOTOR CENTRAL
                # =========================================

                result = (
                    await query_engine.execute(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),

                        bot_version=(
                            bot_version
                        ),

                        telegram_id=(
                            tg_user.id
                        ),

                        username=(
                            tg_user.username
                        ),

                        actor_role=(
                            role
                        ),

                        command=(
                            command
                        ),

                        argument=(
                            argument
                        ),

                        request_id=(
                            request_id
                        ),
                    )
                )

            # =============================================
            # CMD NO EXISTE
            # =============================================

            except QueryCommandNotFoundError:

                await message.answer(
                    "⚠️ <b>COMANDO NO RECONOCIDO</b>\n\n"

                    "Usa /cmds para consultar "
                    "los CMD disponibles."
                )

                return

            # =============================================
            # CMD NO DISPONIBLE EN LA VERSIÓN
            # =============================================

            except QueryCommandDisabledError:

                await message.answer(
                    format_command_not_available()
                )

                return

            # =============================================
            # CUENTA NO REGISTRADA
            # =============================================

            except QueryAccountRequiredError:

                await message.answer(
                    format_account_required()
                )

                return

            # =============================================
            # CUENTA BLOQUEADA
            # =============================================

            except QueryAccountBlockedError:

                await message.answer(
                    format_account_blocked()
                )

                return

            # =============================================
            # SIN PERMISO
            # =============================================

            except QueryPermissionError:

                await message.answer(
                    format_access_denied()
                )

                return

            # =============================================
            # ENTRADA INVÁLIDA
            #
            # NO API
            # NO COBRO
            # =============================================

            except QueryInvalidInputError:

                await message.answer(
                    format_invalid_input(
                        command=command,

                        example=(
                            f"{command} DATO"
                        ),
                    )
                )

                return

            # =============================================
            # SIN CRÉDITOS
            # =============================================

            except InsufficientCreditsError:

                await message.answer(
                    "💳 <b>CRÉDITOS INSUFICIENTES</b>\n\n"

                    "No tienes saldo suficiente "
                    "para ejecutar este CMD.\n\n"

                    "Utiliza /buy para consultar "
                    "las opciones disponibles."
                )

                return

            # =============================================
            # LÍMITE DIARIO
            # =============================================

            except QueryDailyLimitError as exc:

                await message.answer(
                    "⏳ <b>LÍMITE DIARIO ALCANZADO</b>\n\n"

                    f"{escape(str(exc))}"
                )

                return

            # =============================================
            # PROVEEDOR NO CONFIGURADO
            #
            # NO COBRO
            # =============================================

            except QueryProviderNotConfiguredError:

                await message.answer(
                    format_service_unavailable()
                )

                return

            # =============================================
            # FALLO TÉCNICO PROVEEDOR
            #
            # query_engine.py se encarga
            # del reembolso si ya hubo cobro.
            # =============================================

            except QueryProviderError:

                await message.answer(
                    format_service_unavailable()
                )

                return

            # =============================================
            # BOT APAGADO / MANTENIMIENTO
            # =============================================

            except QueryBotUnavailableError:

                await message.answer(
                    "🛠️ <b>SERVICIO NO DISPONIBLE</b>\n\n"

                    "Este bot no se encuentra "
                    "habilitado para consultas "
                    "en este momento."
                )

                return

            # =============================================
            # ERROR CONTROLADO GENERAL
            # =============================================

            except QueryEngineError:

                await message.answer(
                    format_service_unavailable()
                )

                return

            # =============================================
            # ERROR INESPERADO
            # =============================================

            except Exception:

                await message.answer(
                    format_service_unavailable()
                )

                return

            # =============================================
            # SIN RESULTADOS
            #
            # Si la consulta fue válida y llegó
            # correctamente al proveedor,
            # query_engine ya aplicó la política
            # de cobro correspondiente.
            # =============================================

            if result.no_results:

                await message.answer(
                    format_no_results(
                        bot_name=(
                            bot_name
                        ),

                        service=(
                            result.title
                        ),

                        cost=(
                            result.cost
                        ),

                        remaining_credits=(
                            result
                            .remaining_credits
                        ),

                        username=(
                            tg_user.username
                        ),

                        telegram_id=(
                            tg_user.id
                        ),
                    )
                )

                return

            # =============================================
            # DATOS DEL PROVEEDOR
            # =============================================

            provider_data = (
                result
                .provider_result
                .data
            )

            content_type = (
                result
                .provider_result
                .content_type
            )

            # =============================================
            # ARCHIVO / PDF / IMAGEN
            # =============================================

            if isinstance(
                provider_data,
                (
                    bytes,
                    bytearray,
                ),
            ):

                try:

                    await _send_binary_result(
                        message,

                        command=(
                            command
                        ),

                        content=bytes(
                            provider_data
                        ),

                        content_type=(
                            content_type
                        ),
                    )

                    result_text = (
                        "Archivo recibido "
                        "correctamente."
                    )

                except Exception:

                    result_text = (
                        "La consulta fue completada, "
                        "pero el archivo no pudo "
                        "enviarse por Telegram."
                    )

            # =============================================
            # TEXTO / JSON
            # =============================================

            else:

                result_text = (
                    await _prepare_text_result(
                        message,

                        command=(
                            command
                        ),

                        data=(
                            provider_data
                        ),
                    )
                )

            # =============================================
            # RESUMEN FINAL
            # =============================================

            await message.answer(
                format_query_result(
                    bot_name=(
                        bot_name
                    ),

                    service=(
                        result.title
                    ),

                    level=(
                        result.level
                    ),

                    result=(
                        result_text
                    ),

                    cost=(
                        result.cost
                    ),

                    remaining_credits=(
                        result
                        .remaining_credits
                    ),

                    username=(
                        tg_user.username
                    ),

                    telegram_id=(
                        tg_user.id
                    ),
                )
            )

    return router
