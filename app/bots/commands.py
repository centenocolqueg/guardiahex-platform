from __future__ import annotations

import uuid
from datetime import datetime, timezone
from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.catalog import (
    CATEGORY_META,
    get_commands_for_version,
    get_enabled_categories,
)
from app.bots.permissions import (
    Role,
    can_grant_credits,
    can_manage_bans,
    can_manage_role,
    can_manage_sellers,
    can_use_sub,
    can_view_statistics,
    has_permission,
    normalize_role,
    role_level,
)
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.role import RoleModel
from app.models.transaction import TransactionModel
from app.models.user import UserModel
from app.services.credits import (
    CreditError,
    InsufficientCreditsError,
    InvalidCreditAmountError,
    UnauthorizedCreditOperationError,
    UserNotFoundError,
    credit_service,
)
from app.services.sellers import (
    SellerError,
    seller_service,
)
from app.services.subscriptions import (
    SubscriptionError,
    subscription_service,
)


# =========================================================
# CONSTANTES
# =========================================================

WELCOME_BONUS = 5

STAFF_ROLE_NAMES = {
    "SUPERADMIN",
    "OWNER",
    "FUNDADOR",
    "COFUNDADOR",
    "ADMIN",
}


# =========================================================
# UTILIDADES
# =========================================================

def _username_text(
    username: str | None,
) -> str:
    if not username:
        return "Sin username"

    return f"@{escape(username)}"


def _normalize_version_safe(
    version: str | None,
) -> str:
    value = (
        str(version or "V1")
        .strip()
        .upper()
    )

    if value not in {
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
    }:
        return "V1"

    return value


def _parse_positive_int(
    value: str,
) -> int | None:
    try:
        result = int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if result <= 0:
        return None

    return result


def _superadmin_telegram_id() -> int | None:
    value = getattr(
        settings,
        "superadmin_telegram_id",
        None,
    )

    if value in {
        None,
        "",
        0,
        "0",
    }:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _is_global_superadmin(
    *,
    telegram_id: int,
    is_master_bot: bool,
) -> bool:
    configured_id = (
        _superadmin_telegram_id()
    )

    return bool(
        is_master_bot
        and configured_id is not None
        and telegram_id == configured_id
    )


# =========================================================
# USUARIOS
# =========================================================

async def _get_user(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
    for_update: bool = False,
) -> UserModel | None:

    statement = (
        select(UserModel)
        .where(
            UserModel.bot_id == bot_id,
            UserModel.telegram_id
            == telegram_id,
        )
    )

    if for_update:
        statement = (
            statement.with_for_update()
        )

    result = await session.execute(
        statement
    )

    return (
        result.scalar_one_or_none()
    )


async def _ensure_user_role(
    session: AsyncSession,
    *,
    bot_id: int,
    user_id: int,
) -> RoleModel:

    result = await session.execute(
        select(RoleModel)
        .where(
            RoleModel.bot_id == bot_id,
            RoleModel.user_id == user_id,
            RoleModel.role == "USER",
        )
    )

    role = (
        result.scalar_one_or_none()
    )

    if role is None:
        role = RoleModel(
            bot_id=bot_id,
            user_id=user_id,
            role="USER",
            is_active=True,
            assigned_by_role="SYSTEM",
        )

        session.add(role)

    elif not role.is_active:
        role.is_active = True
        role.revoked_at = None

    return role


async def _register_user(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> tuple[
    UserModel,
    bool,
    bool,
]:
    """
    Retorna:
    - usuario
    - fue creado
    - recibió bono
    """

    now = datetime.now(
        timezone.utc
    )

    user = await _get_user(
        session,
        bot_id=bot_id,
        telegram_id=telegram_id,
        for_update=True,
    )

    created = False
    bonus_granted = False

    # =====================================================
    # NUEVO USUARIO
    # =====================================================

    if user is None:
        user = UserModel(
            bot_id=bot_id,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            credits=0,
            current_plan="FREE",
            is_registered=True,
            welcome_bonus_received=False,
            is_active=True,
            is_banned=False,
            last_seen_at=now,
        )

        session.add(user)

        await session.flush()

        created = True

    # =====================================================
    # USUARIO EXISTENTE
    # =====================================================

    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_registered = True
        user.last_seen_at = now

    # =====================================================
    # ROL USER
    # =====================================================

    await _ensure_user_role(
        session,
        bot_id=bot_id,
        user_id=user.id,
    )

    # =====================================================
    # BONO ÚNICO
    # =====================================================

    if not user.welcome_bonus_received:

        previous_balance = int(
            user.credits
        )

        user.credits = (
            previous_balance
            + WELCOME_BONUS
        )

        user.welcome_bonus_received = True

        transaction = TransactionModel(
            bot_id=bot_id,

            transaction_type=(
                "WELCOME_BONUS"
            ),

            status="COMPLETED",

            source_user_id=None,
            target_user_id=user.id,

            credits=WELCOME_BONUS,

            target_previous_balance=(
                previous_balance
            ),

            target_final_balance=(
                user.credits
            ),

            performed_by_telegram_id=None,
            performed_by_role="SYSTEM",

            reference=(
                "BONUS-"
                f"{uuid.uuid4().hex.upper()}"
            ),

            description=(
                "Bono único de registro."
            ),
        )

        session.add(
            transaction
        )

        bonus_granted = True

    await session.commit()

    await session.refresh(
        user
    )

    return (
        user,
        created,
        bonus_granted,
    )


# =========================================================
# ROLES
# =========================================================

async def _get_active_roles(
    session: AsyncSession,
    *,
    bot_id: int,
    user_id: int,
) -> list[str]:

    result = await session.execute(
        select(
            RoleModel.role
        )
        .where(
            RoleModel.bot_id == bot_id,
            RoleModel.user_id == user_id,
            RoleModel.is_active.is_(True),
        )
    )

    return [
        str(role)
        .strip()
        .upper()
        for role
        in result.scalars().all()
    ]


def _highest_role(
    roles: list[str],
) -> str:

    best = "USER"

    best_level = role_level(
        Role.USER
    )

    for value in roles:

        try:
            normalized = normalize_role(
                value
            )

        except ValueError:
            continue

        level = role_level(
            normalized
        )

        if level > best_level:
            best = normalized.value
            best_level = level

    return best


async def _effective_role(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
    is_master_bot: bool,
    user: UserModel | None = None,
) -> str:

    if _is_global_superadmin(
        telegram_id=telegram_id,
        is_master_bot=is_master_bot,
    ):
        return "SUPERADMIN"

    if user is None:
        user = await _get_user(
            session,
            bot_id=bot_id,
            telegram_id=telegram_id,
        )

    if user is None:
        return "USER"

    roles = await _get_active_roles(
        session,
        bot_id=bot_id,
        user_id=user.id,
    )

    return _highest_role(
        roles
    )


async def _target_highest_role(
    session: AsyncSession,
    *,
    bot_id: int,
    target: UserModel,
    target_telegram_id: int,
    is_master_bot: bool,
) -> str:

    return await _effective_role(
        session,
        bot_id=bot_id,
        telegram_id=target_telegram_id,
        is_master_bot=is_master_bot,
        user=target,
    )


# =========================================================
# CUENTA OPERATIVA
# =========================================================

async def _require_registered_actor(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
) -> UserModel | None:

    user = await _get_user(
        session,
        bot_id=bot_id,
        telegram_id=telegram_id,
    )

    if user is None:
        return None

    if not user.is_registered:
        return None

    return user


def _account_operational(
    user: UserModel,
) -> bool:

    return bool(
        user.is_registered
        and user.is_active
        and not user.is_banned
    )


# =========================================================
# ROUTER
# =========================================================

def get_commands_router() -> Router:

    router = Router(
        name="guardiahex_commands"
    )

    # =====================================================
    # /start
    # =====================================================

    @router.message(
        CommandStart()
    )
    async def command_start(
        message: Message,
        internal_bot_id: int,
        bot_version: str,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        async with AsyncSessionLocal() as session:

            user = await _get_user(
                session,
                bot_id=internal_bot_id,
                telegram_id=tg_user.id,
            )

            if user is not None:

                user.last_seen_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

                user.username = (
                    tg_user.username
                )

                user.first_name = (
                    tg_user.first_name
                )

                user.last_name = (
                    tg_user.last_name
                )

                try:
                    await session.commit()

                except Exception:
                    await session.rollback()

        username = _username_text(
            tg_user.username
        )

        version = (
            _normalize_version_safe(
                bot_version
            )
        )

        text = (
            "🛡️ <b>GUARDIAHEXBOT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"Bienvenido, <b>{username}</b> 👋\n\n"

            "Sistema de servicios y herramientas "
            "integrado directamente con Telegram.\n\n"

            f"VERSIÓN ➾ <b>{version}</b>\n\n"

            "<b>COMANDOS PRINCIPALES</b>\n\n"

            "/register ➾ Registrar cuenta\n"
            "/cmds ➾ Catálogo disponible\n"
            "/me ➾ Mi cuenta\n"
            "/buy ➾ Planes y créditos\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            "🔐 Las operaciones administrativas "
            "están protegidas por roles.\n\n"

            "Si eres nuevo utiliza "
            "<b>/register</b>."
        )

        await message.answer(
            text
        )

    # =====================================================
    # /register
    # =====================================================

    @router.message(
        Command("register")
    )
    async def command_register(
        message: Message,
        internal_bot_id: int,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        try:
            async with AsyncSessionLocal() as session:

                (
                    user,
                    created,
                    bonus_granted,
                ) = await _register_user(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),

                    telegram_id=(
                        tg_user.id
                    ),

                    username=(
                        tg_user.username
                    ),

                    first_name=(
                        tg_user.first_name
                    ),

                    last_name=(
                        tg_user.last_name
                    ),
                )

        except IntegrityError:

            await message.answer(
                "⚠️ Se detectó un registro "
                "simultáneo.\n\n"
                "Intenta nuevamente."
            )

            return

        except Exception:

            await message.answer(
                "⚠️ <b>REGISTRO NO DISPONIBLE</b>\n\n"
                "No fue posible completar el "
                "registro en este momento."
            )

            return

        if created:
            status_text = (
                "Cuenta creada correctamente ✅"
            )

        else:
            status_text = (
                "Tu cuenta ya estaba registrada ✅"
            )

        if bonus_granted:
            bonus_text = (
                f"+{WELCOME_BONUS} créditos 🎁"
            )

        else:
            bonus_text = (
                "Bono de registro ya utilizado"
            )

        await message.answer(
            "✅ <b>REGISTRO COMPLETADO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"{status_text}\n\n"

            f"USUARIO ➾ "
            f"<b>{_username_text(tg_user.username)}</b>\n"

            f"TELEGRAM ID ➾ "
            f"<code>{tg_user.id}</code>\n"

            f"CRÉDITOS ➾ "
            f"<b>{user.credits}</b>\n"

            f"BONO ➾ "
            f"<b>{bonus_text}</b>\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    # =====================================================
    # /cmds
    # =====================================================

    @router.message(
        Command("cmds")
    )
    async def command_cmds(
        message: Message,
        bot_version: str,
    ) -> None:

        version = (
            _normalize_version_safe(
                bot_version
            )
        )

        categories = (
            get_enabled_categories(
                version
            )
        )

        commands = (
            get_commands_for_version(
                version
            )
        )

        command_counts: dict[
            str,
            int,
        ] = {
            category: 0
            for category
            in categories
        }

        for command in commands:

            if (
                command.category
                in command_counts
            ):
                command_counts[
                    command.category
                ] += 1

        lines = [
            "🔎 <b>SISTEMA DE COMANDOS</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"VERSIÓN ➾ <b>{version}</b>",
            (
                "CATEGORÍAS ➾ "
                f"<b>{len(categories)}</b>"
            ),
            (
                "CMD HABILITADOS ➾ "
                f"<b>{len(commands)}</b>"
            ),
            "",
        ]

        for category in categories:

            meta = (
                CATEGORY_META[
                    category
                ]
            )

            icon = str(
                meta["icon"]
            )

            title = str(
                meta["title"]
            )

            count = (
                command_counts[
                    category
                ]
            )

            lines.append(
                f"{icon} <b>{title}</b> "
                f"➾ {count} CMD"
            )

        lines.extend(
            [
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                (
                    "Cada categoría muestra "
                    "máximo 3 CMD por página."
                ),
            ]
        )

        await message.answer(
            "\n".join(lines)
        )

    # =====================================================
    # /me
    # =====================================================

    @router.message(
        Command("me")
    )
    async def command_me(
        message: Message,
        internal_bot_id: int,
        bot_version: str,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        async with AsyncSessionLocal() as session:

            user = await _get_user(
                session,
                bot_id=internal_bot_id,
                telegram_id=tg_user.id,
            )

            if user is None:

                await message.answer(
                    "👤 <b>CUENTA NO REGISTRADA</b>\n\n"
                    "Utiliza /register para crear "
                    "tu cuenta."
                )

                return

            role = await _effective_role(
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

                user=user,
            )

            user.last_seen_at = (
                datetime.now(
                    timezone.utc
                )
            )

            try:
                await session.commit()

            except Exception:
                await session.rollback()

            if user.is_banned:
                state = "BLOQUEADO ⛔"

            elif not user.is_active:
                state = "INACTIVO ⚠️"

            else:
                state = "ACTIVO ✅"

            if (
                user.plan_expires_at
                is None
            ):
                expires = "Sin vencimiento"

            else:
                expires = (
                    user.plan_expires_at
                    .strftime(
                        "%d/%m/%Y %H:%M UTC"
                    )
                )

            await message.answer(
                "👤 <b>MI CUENTA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"USUARIO ➾ "
                f"<b>{_username_text(tg_user.username)}</b>\n"

                f"ID ➾ "
                f"<code>{tg_user.id}</code>\n"

                f"ROL ➾ "
                f"<b>{escape(role)}</b>\n"

                f"VERSIÓN BOT ➾ "
                f"<b>{_normalize_version_safe(bot_version)}</b>\n"

                f"PLAN ➾ "
                f"<b>{escape(user.current_plan)}</b>\n"

                f"VENCE ➾ "
                f"<b>{expires}</b>\n"

                f"CRÉDITOS ➾ "
                f"<b>{user.credits}</b>\n"

                f"CONSULTAS ➾ "
                f"<b>{user.total_queries}</b>\n"

                f"CRÉDITOS GASTADOS ➾ "
                f"<b>{user.total_credits_spent}</b>\n"

                f"ESTADO ➾ "
                f"<b>{state}</b>\n\n"

                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

    # =====================================================
    # /buy
    # =====================================================

    @router.message(
        Command("buy")
    )
    async def command_buy(
        message: Message,
    ) -> None:

        await message.answer(
            "💎 <b>PLANES DE CRÉDITOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "🔰 <b>BÁSICO</b>\n"
            "50 + 20 ➾ S/10\n"
            "200 + 50 ➾ S/15\n"
            "350 + 80 ➾ S/20\n\n"

            "⭐️ <b>STANDARD</b>\n"
            "500 + 100 ➾ S/50\n"
            "800 + 150 ➾ S/60\n"
            "1000 + 200 ➾ S/70\n\n"

            "💎 <b>PREMIUM</b>\n"
            "1500 + 300 ➾ S/90\n"
            "2000 + 400 ➾ S/120\n"
            "3000 + 600 ➾ S/180\n\n"

            "👑 <b>SELLER</b>\n"
            "3200 créditos ➾ S/120\n"
            "Sin vencimiento\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Compra únicamente con personal "
            "autorizado."
        )

    # =====================================================
    # /cred
    # =====================================================

    @router.message(
        Command("cred")
    )
    async def command_cred(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        parts = (
            message.text or ""
        ).split()

        if len(parts) != 3:

            await message.answer(
                "ℹ️ <b>USO CORRECTO</b>\n\n"
                "<code>/cred TELEGRAM_ID CANTIDAD</code>"
            )

            return

        target_telegram_id = (
            _parse_positive_int(
                parts[1]
            )
        )

        amount = (
            _parse_positive_int(
                parts[2]
            )
        )

        if (
            target_telegram_id is None
            or amount is None
        ):
            await message.answer(
                "⚠️ ID o cantidad inválida."
            )

            return

        async with AsyncSessionLocal() as session:

            actor = (
                await _require_registered_actor(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),

                    telegram_id=(
                        tg_user.id
                    ),
                )
            )

            global_superadmin = (
                _is_global_superadmin(
                    telegram_id=(
                        tg_user.id
                    ),

                    is_master_bot=(
                        is_master_bot
                    ),
                )
            )

            if (
                actor is None
                and not global_superadmin
            ):
                await message.answer(
                    "⚠️ Primero utiliza /register."
                )

                return

            if (
                actor is not None
                and not _account_operational(
                    actor
                )
                and not global_superadmin
            ):
                await message.answer(
                    "⛔ Tu cuenta no está habilitada."
                )

                return

            role = await _effective_role(
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

                user=actor,
            )

            try:

                # =========================================
                # SELLER
                # =========================================

                if role == "SELLER":

                    transaction = (
                        await seller_service
                        .transfer_from_seller(
                            session,

                            bot_id=(
                                internal_bot_id
                            ),

                            seller_telegram_id=(
                                tg_user.id
                            ),

                            target_telegram_id=(
                                target_telegram_id
                            ),

                            amount=amount,
                        )
                    )

                    await message.answer(
                        "✅ <b>TRANSFERENCIA COMPLETADA</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                        f"DESTINO ➾ "
                        f"<code>{target_telegram_id}</code>\n"

                        f"CRÉDITOS ➾ "
                        f"<b>{amount}</b>\n"

                        f"REFERENCIA ➾ "
                        f"<code>{transaction.reference}</code>\n\n"

                        "El saldo fue descontado "
                        "de tu cuenta SELLER."
                    )

                    return

                # =========================================
                # STAFF CON PERMISO
                # =========================================

                if not can_grant_credits(
                    role
                ):
                    await message.answer(
                        "⛔ <b>ACCESO DENEGADO</b>\n\n"
                        "No tienes permisos para "
                        "asignar créditos."
                    )

                    return

                target = (
                    await seller_service
                    .get_user_by_telegram_id(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),

                        telegram_id=(
                            target_telegram_id
                        ),
                    )
                )

                if not _account_operational(
                    target
                ):
                    await message.answer(
                        "⛔ El usuario destino "
                        "no está habilitado."
                    )

                    return

                transaction = (
                    await credit_service
                    .add_credits(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),

                        target_user_id=(
                            target.id
                        ),

                        amount=amount,

                        performed_by_telegram_id=(
                            tg_user.id
                        ),

                        performed_by_role=(
                            role
                        ),

                        transaction_type=(
                            "ADMIN_CREDIT_GRANT"
                        ),

                        description=(
                            "Asignación administrativa "
                            "de créditos."
                        ),
                    )
                )

                await message.answer(
                    "✅ <b>CRÉDITOS ASIGNADOS</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                    f"DESTINO ➾ "
                    f"<code>{target_telegram_id}</code>\n"

                    f"CANTIDAD ➾ "
                    f"<b>{amount}</b>\n"

                    f"NUEVO SALDO ➾ "
                    f"<b>{transaction.target_final_balance}</b>\n"

                    f"REFERENCIA ➾ "
                    f"<code>{transaction.reference}</code>"
                )

            except (
                UserNotFoundError,
                InsufficientCreditsError,
                InvalidCreditAmountError,
                UnauthorizedCreditOperationError,
                SellerError,
                CreditError,
            ) as exc:

                await message.answer(
                    "⚠️ <b>OPERACIÓN RECHAZADA</b>\n\n"
                    f"{escape(str(exc))}"
                )

    # =====================================================
    # /seller
    # =====================================================

    @router.message(
        Command("seller")
    )
    async def command_seller(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        parts = (
            message.text or ""
        ).split()

        if len(parts) != 2:

            await message.answer(
                "ℹ️ <b>USO CORRECTO</b>\n\n"
                "<code>/seller TELEGRAM_ID</code>"
            )

            return

        target_id = (
            _parse_positive_int(
                parts[1]
            )
        )

        if target_id is None:
            await message.answer(
                "⚠️ Telegram ID inválido."
            )

            return

        async with AsyncSessionLocal() as session:

            role = await _effective_role(
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

            if not can_manage_sellers(
                role
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            try:

                await seller_service.assign_seller(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),

                    target_telegram_id=(
                        target_id
                    ),

                    assigned_by_telegram_id=(
                        tg_user.id
                    ),

                    assigned_by_role=role,
                )

            except (
                SellerError,
                UserNotFoundError,
            ) as exc:

                await message.answer(
                    "⚠️ <b>NO SE PUDO ASIGNAR SELLER</b>\n\n"
                    f"{escape(str(exc))}"
                )

                return

            await message.answer(
                "👑 <b>SELLER ACTIVADO</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"Telegram ID ➾ "
                f"<code>{target_id}</code>"
            )

    # =====================================================
    # /unseller
    # =====================================================

    @router.message(
        Command("unseller")
    )
    async def command_unseller(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        parts = (
            message.text or ""
        ).split()

        if len(parts) != 2:

            await message.answer(
                "ℹ️ <b>USO CORRECTO</b>\n\n"
                "<code>/unseller TELEGRAM_ID</code>"
            )

            return

        target_id = (
            _parse_positive_int(
                parts[1]
            )
        )

        if target_id is None:
            await message.answer(
                "⚠️ Telegram ID inválido."
            )

            return

        async with AsyncSessionLocal() as session:

            role = await _effective_role(
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

            if not can_manage_sellers(
                role
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            try:

                await seller_service.remove_seller(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),

                    target_telegram_id=(
                        target_id
                    ),

                    removed_by_role=(
                        role
                    ),
                )

            except (
                SellerError,
                UserNotFoundError,
            ) as exc:

                await message.answer(
                    "⚠️ <b>NO SE PUDO RETIRAR SELLER</b>\n\n"
                    f"{escape(str(exc))}"
                )

                return

            await message.answer(
                "✅ <b>SELLER RETIRADO</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"Telegram ID ➾ "
                f"<code>{target_id}</code>\n\n"

                "Sus créditos permanecen intactos."
            )

    # =====================================================
    # /sellers
    # =====================================================

    @router.message(
        Command("sellers")
    )
    async def command_sellers(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        async with AsyncSessionLocal() as session:

            role = await _effective_role(
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

            if not can_manage_sellers(
                role
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            sellers = (
                await seller_service
                .list_sellers(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),
                )
            )

            if not sellers:

                await message.answer(
                    "👑 <b>SELLERS</b>\n\n"
                    "No existen SELLERS activos."
                )

                return

            lines = [
                "👑 <b>SELLERS ACTIVOS</b>",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
            ]

            for index, seller in enumerate(
                sellers,
                start=1,
            ):

                username = (
                    _username_text(
                        seller.username
                    )
                )

                lines.extend(
                    [
                        (
                            f"{index}. "
                            f"<b>{username}</b>"
                        ),
                        (
                            "ID ➾ "
                            f"<code>{seller.telegram_id}</code>"
                        ),
                        (
                            "SALDO ➾ "
                            f"<b>{seller.credits}</b>"
                        ),
                        "",
                    ]
                )

            lines.append(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

            await message.answer(
                "\n".join(lines)
            )

    # =====================================================
    # /ban
    # =====================================================

    @router.message(
        Command("ban")
    )
    async def command_ban(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        parts = (
            message.text or ""
        ).split(
            maxsplit=2
        )

        if len(parts) < 2:

            await message.answer(
                "ℹ️ <b>USO CORRECTO</b>\n\n"
                "<code>/ban TELEGRAM_ID MOTIVO</code>"
            )

            return

        target_id = (
            _parse_positive_int(
                parts[1]
            )
        )

        reason = (
            parts[2].strip()
            if len(parts) >= 3
            else "Sin motivo especificado"
        )

        if target_id is None:
            await message.answer(
                "⚠️ Telegram ID inválido."
            )

            return

        async with AsyncSessionLocal() as session:

            actor_role = (
                await _effective_role(
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

            if not can_manage_bans(
                actor_role
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            target = await _get_user(
                session,

                bot_id=(
                    internal_bot_id
                ),

                telegram_id=(
                    target_id
                ),

                for_update=True,
            )

            if target is None:

                await message.answer(
                    "⚠️ Usuario no registrado."
                )

                return

            target_role = (
                await _target_highest_role(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),

                    target=target,

                    target_telegram_id=(
                        target_id
                    ),

                    is_master_bot=(
                        is_master_bot
                    ),
                )
            )

            if not can_manage_role(
                actor_role,
                target_role,
            ):
                await message.answer(
                    "⛔ No puedes bloquear a "
                    "un rol igual o superior al tuyo."
                )

                return

            target.is_banned = True

            target.ban_reason = (
                reason[:255]
            )

            target.banned_at = (
                datetime.now(
                    timezone.utc
                )
            )

            try:
                await session.commit()

            except Exception:
                await session.rollback()
                raise

            await message.answer(
                "⛔ <b>USUARIO BLOQUEADO</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"ID ➾ "
                f"<code>{target_id}</code>\n"

                f"MOTIVO ➾ "
                f"{escape(reason[:255])}"
            )

    # =====================================================
    # /unban
    # =====================================================

    @router.message(
        Command("unban")
    )
    async def command_unban(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        parts = (
            message.text or ""
        ).split()

        if len(parts) != 2:

            await message.answer(
                "ℹ️ <b>USO CORRECTO</b>\n\n"
                "<code>/unban TELEGRAM_ID</code>"
            )

            return

        target_id = (
            _parse_positive_int(
                parts[1]
            )
        )

        if target_id is None:
            await message.answer(
                "⚠️ Telegram ID inválido."
            )

            return

        async with AsyncSessionLocal() as session:

            actor_role = (
                await _effective_role(
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

            if not can_manage_bans(
                actor_role
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            target = await _get_user(
                session,

                bot_id=(
                    internal_bot_id
                ),

                telegram_id=(
                    target_id
                ),

                for_update=True,
            )

            if target is None:

                await message.answer(
                    "⚠️ Usuario no registrado."
                )

                return

            target_role = (
                await _target_highest_role(
                    session,

                    bot_id=(
                        internal_bot_id
                    ),

                    target=target,

                    target_telegram_id=(
                        target_id
                    ),

                    is_master_bot=(
                        is_master_bot
                    ),
                )
            )

            if not can_manage_role(
                actor_role,
                target_role,
            ):
                await message.answer(
                    "⛔ No puedes modificar a "
                    "un rol igual o superior al tuyo."
                )

                return

            target.is_banned = False
            target.ban_reason = None
            target.banned_at = None

            try:
                await session.commit()

            except Exception:
                await session.rollback()
                raise

            await message.answer(
                "✅ <b>USUARIO DESBLOQUEADO</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"ID ➾ "
                f"<code>{target_id}</code>"
            )

    # =====================================================
    # /staff
    # =====================================================

    @router.message(
        Command("staff")
    )
    async def command_staff(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        async with AsyncSessionLocal() as session:

            actor_role = (
                await _effective_role(
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

            if not has_permission(
                actor_role,
                "view_staff",
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            result = await session.execute(
                select(
                    UserModel,
                    RoleModel,
                )
                .join(
                    RoleModel,
                    (
                        RoleModel.user_id
                        == UserModel.id
                    )
                    & (
                        RoleModel.bot_id
                        == UserModel.bot_id
                    ),
                )
                .where(
                    UserModel.bot_id
                    == internal_bot_id,

                    UserModel.is_active
                    .is_(True),

                    UserModel.is_banned
                    .is_(False),

                    RoleModel.is_active
                    .is_(True),

                    RoleModel.role.in_(
                        STAFF_ROLE_NAMES
                    ),
                )
                .order_by(
                    RoleModel.role.asc(),
                    UserModel.id.asc(),
                )
            )

            rows = result.all()

            if not rows:

                await message.answer(
                    "👥 <b>STAFF</b>\n\n"
                    "No existe staff registrado."
                )

                return

            lines = [
                "👥 <b>STAFF AUTORIZADO</b>",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
            ]

            for user, role in rows:

                lines.extend(
                    [
                        (
                            "👤 "
                            f"<b>{_username_text(user.username)}</b>"
                        ),
                        (
                            "ROL ➾ "
                            f"<b>{escape(role.normalized_role)}</b>"
                        ),
                        (
                            "ID ➾ "
                            f"<code>{user.telegram_id}</code>"
                        ),
                        "",
                    ]
                )

            lines.append(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

            await message.answer(
                "\n".join(lines)
            )

    # =====================================================
    # /estadisticas
    # =====================================================

    @router.message(
        Command("estadisticas")
    )
    async def command_statistics(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        async with AsyncSessionLocal() as session:

            actor_role = (
                await _effective_role(
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

            if not can_view_statistics(
                actor_role
            ):
                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

            result = await session.execute(
                select(
                    func.count(
                        UserModel.id
                    ),
                    func.coalesce(
                        func.sum(
                            UserModel.total_queries
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            UserModel.credits
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            UserModel.total_credits_spent
                        ),
                        0,
                    ),
                )
                .where(
                    UserModel.bot_id
                    == internal_bot_id
                )
            )

            (
                users_count,
                total_queries,
                credits_in_accounts,
                total_spent,
            ) = result.one()

            seller_result = (
                await session.execute(
                    select(
                        func.count(
                            RoleModel.id
                        )
                    )
                    .where(
                        RoleModel.bot_id
                        == internal_bot_id,

                        RoleModel.role
                        == "SELLER",

                        RoleModel.is_active
                        .is_(True),
                    )
                )
            )

            seller_count = int(
                seller_result.scalar_one()
                or 0
            )

            await message.answer(
                "📊 <b>ESTADÍSTICAS DEL BOT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"👥 USUARIOS ➾ "
                f"<b>{int(users_count or 0)}</b>\n"

                f"🔎 CONSULTAS ➾ "
                f"<b>{int(total_queries or 0)}</b>\n"

                f"💳 CRÉDITOS EN CUENTAS ➾ "
                f"<b>{int(credits_in_accounts or 0)}</b>\n"

                f"💸 CRÉDITOS CONSUMIDOS ➾ "
                f"<b>{int(total_spent or 0)}</b>\n"

                f"👑 SELLERS ➾ "
                f"<b>{seller_count}</b>\n\n"

                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

    # =====================================================
    # /sub
    # =====================================================

    @router.message(
        Command("sub")
    )
    async def command_sub(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        # Admite nombres de plan con espacios.
        #
        # /sub 123456789 30 PREMIUM
        # /sub 123456789 30 PREMIUM PLUS

        parts = (
            message.text or ""
        ).split(
            maxsplit=3
        )

        if len(parts) != 4:

            await message.answer(
                "ℹ️ <b>USO CORRECTO</b>\n\n"

                "<code>"
                "/sub TELEGRAM_ID DIAS PLAN"
                "</code>\n\n"

                "Ejemplo:\n"

                "<code>"
                "/sub 123456789 30 PREMIUM"
                "</code>"
            )

            return

        target_telegram_id = (
            _parse_positive_int(
                parts[1]
            )
        )

        days = (
            _parse_positive_int(
                parts[2]
            )
        )

        plan = (
            parts[3]
            .strip()
            .upper()
        )

        if target_telegram_id is None:

            await message.answer(
                "⚠️ Telegram ID inválido."
            )

            return

        if days is None:

            await message.answer(
                "⚠️ La cantidad de días "
                "debe ser mayor que cero."
            )

            return

        if not plan:

            await message.answer(
                "⚠️ Debes indicar un plan."
            )

            return

        async with AsyncSessionLocal() as session:

            role = await _effective_role(
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

            if not can_use_sub(
                role
            ):

                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>\n\n"

                    "Tu rol no puede administrar "
                    "suscripciones."
                )

                return

            try:

                subscription = (
                    await subscription_service
                    .add_subscription(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),

                        target_telegram_id=(
                            target_telegram_id
                        ),

                        days=days,

                        plan=plan,

                        activated_by_telegram_id=(
                            tg_user.id
                        ),

                        activated_by_role=(
                            role
                        ),
                    )
                )

                status_data = (
                    await subscription_service
                    .get_subscription_status(
                        session,

                        bot_id=(
                            internal_bot_id
                        ),

                        telegram_id=(
                            target_telegram_id
                        ),
                    )
                )

            except SubscriptionError as exc:

                await message.answer(
                    "⚠️ <b>SUSCRIPCIÓN RECHAZADA</b>\n\n"
                    f"{escape(str(exc))}"
                )

                return

            except Exception:

                await message.answer(
                    "⚠️ <b>ERROR DE SUSCRIPCIÓN</b>\n\n"

                    "No fue posible completar "
                    "la operación."
                )

                return

            expires_at = (
                subscription.expires_at
            )

            if expires_at is not None:

                expiration_text = (
                    expires_at.strftime(
                        "%d/%m/%Y %H:%M UTC"
                    )
                )

            else:
                expiration_text = (
                    "No disponible"
                )

            await message.answer(
                "✅ <b>SUSCRIPCIÓN ACTIVADA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                f"USUARIO ➾ "
                f"<code>{target_telegram_id}</code>\n"

                f"PLAN ➾ "
                f"<b>{escape(subscription.plan_name)}</b>\n"

                f"DÍAS AÑADIDOS ➾ "
                f"<b>{subscription.days_added}</b>\n"

                f"DÍAS RESTANTES ➾ "
                f"<b>{status_data['remaining_days']}</b>\n"

                f"VENCE ➾ "
                f"<b>{expiration_text}</b>\n"

                f"CRÉDITOS ➾ "
                f"<b>{status_data['credits']}</b>\n\n"

                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                "✅ Los créditos permanecen "
                "sin modificaciones."
            )

    # =====================================================
    # /anuncio
    # =====================================================

    @router.message(
        Command("anuncio")
    )
    async def command_announcement(
        message: Message,
        internal_bot_id: int,
        is_master_bot: bool,
    ) -> None:

        tg_user = (
            message.from_user
        )

        if tg_user is None:
            return

        async with AsyncSessionLocal() as session:

            role = await _effective_role(
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

            if not has_permission(
                role,
                "send_announcements",
            ):

                await message.answer(
                    "⛔ <b>ACCESO DENEGADO</b>"
                )

                return

        await message.answer(
            "🛠️ <b>MÓDULO DE ANUNCIOS</b>\n\n"

            "Permiso validado correctamente.\n\n"

            "El envío masivo será conectado "
            "al módulo correspondiente."
        )

    return router
