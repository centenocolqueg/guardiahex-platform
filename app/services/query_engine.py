from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.permissions import has_permission
from app.models.audit import AuditModel
from app.models.bot import BotModel
from app.models.command import (
    BotCommandModel,
    CommandModel,
)
from app.models.user import UserModel
from app.services.audit import audit_service
from app.services.credits import (
    InsufficientCreditsError,
    credit_service,
)
from app.services.fuentesdata import (
    ProviderResult,
    fuentesdata_service,
)


# =========================================================
# ERRORES
# =========================================================

class QueryEngineError(Exception):
    """Error general del motor de consultas."""


class QueryCommandNotFoundError(QueryEngineError):
    """El CMD solicitado no existe."""


class QueryCommandDisabledError(QueryEngineError):
    """CMD apagado o no incluido en la versión."""


class QueryAccountRequiredError(QueryEngineError):
    """El usuario necesita registrarse."""


class QueryAccountBlockedError(QueryEngineError):
    """La cuenta está bloqueada o inactiva."""


class QueryPermissionError(QueryEngineError):
    """El rol no posee autorización."""


class QueryInvalidInputError(QueryEngineError):
    """Entrada inválida antes de llamar al proveedor."""


class QueryDailyLimitError(QueryEngineError):
    """El bot alcanzó su capacidad diaria."""


class QueryProviderNotConfiguredError(QueryEngineError):
    """Proveedor o ruta aún no configurados."""


class QueryProviderError(QueryEngineError):
    """Fallo técnico del proveedor."""


class QueryBotUnavailableError(QueryEngineError):
    """El bot no está operativo."""


# =========================================================
# RUTA AUTORIZADA DEL PROVEEDOR
# =========================================================

@dataclass(frozen=True, slots=True)
class ProviderRoute:
    """
    Ruta previamente autorizada del proveedor.

    Los endpoints reales únicamente deben añadirse
    cuando exista documentación válida y autorización.
    """

    method: str
    endpoint: str
    argument_key: str

    min_length: int = 1
    max_length: int = 120

    allow_spaces: bool = True
    digits_only: bool = False


# =========================================================
# REGISTRO DE RUTAS
# =========================================================

# Se mantiene vacío hasta disponer de documentación
# autorizada del proveedor.
#
# Ejemplo estructural:
#
# "SERVICIO_EJEMPLO": ProviderRoute(
#     method="GET",
#     endpoint="ruta-autorizada",
#     argument_key="query",
# )

AUTHORIZED_PROVIDER_ROUTES: dict[
    str,
    ProviderRoute,
] = {}


# =========================================================
# CMD EFECTIVO
# =========================================================

@dataclass(slots=True)
class EffectiveCommand:
    model: CommandModel

    enabled: bool

    price: int

    level: str
    title: str

    provider_key: str | None


# =========================================================
# RESULTADO
# =========================================================

@dataclass(slots=True)
class QueryExecutionResult:
    command: str

    title: str
    level: str

    cost: int

    remaining_credits: int

    no_results: bool

    provider_result: ProviderResult

    duration_ms: int


# =========================================================
# MOTOR CENTRAL
# =========================================================

class QueryEngine:
    """
    Motor central de consultas.

    Flujo:

    Telegram
        ↓
    validar bot
        ↓
    validar CMD
        ↓
    validar versión
        ↓
    aplicar configuración del bot
        ↓
    validar usuario
        ↓
    validar permisos
        ↓
    validar límite diario
        ↓
    validar argumento
        ↓
    comprobar proveedor
        ↓
    comprobar saldo
        ↓
    cobrar créditos
        ↓
    llamar proveedor
        ↓
    resultado / sin resultados / error
        ↓
    estadísticas
        ↓
    auditoría

    REGLA DE COBRO:

    - entrada inválida:
      NO cobra.

    - proveedor no configurado:
      NO cobra.

    - error técnico del proveedor:
      reembolsa.

    - resultado válido:
      cobra.

    - consulta válida sin resultados:
      TAMBIÉN cobra.
    """

    # =====================================================
    # NORMALIZAR CMD
    # =====================================================

    @staticmethod
    def _normalize_command(
        command: str,
    ) -> str:

        value = (
            str(command or "")
            .strip()
            .lower()
        )

        if not value:
            raise QueryCommandNotFoundError(
                "Comando vacío."
            )

        if not value.startswith("/"):
            value = f"/{value}"

        return value

    # =====================================================
    # NORMALIZAR VERSIÓN
    # =====================================================

    @staticmethod
    def _normalize_version(
        version: str | None,
    ) -> str:

        value = (
            str(version or "")
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
            raise QueryCommandDisabledError(
                "Versión del bot inválida."
            )

        return value

    # =====================================================
    # NORMALIZAR ROL
    # =====================================================

    @staticmethod
    def _normalize_role(
        role: str | None,
    ) -> str:

        return (
            str(role or "USER")
            .strip()
            .upper()
        )

    # =====================================================
    # OBTENER BOT
    # =====================================================

    async def _get_bot(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
    ) -> BotModel:

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
            raise QueryBotUnavailableError(
                "Bot no encontrado."
            )

        if not bot.enabled:
            raise QueryBotUnavailableError(
                "Bot deshabilitado."
            )

        if bot.maintenance_mode:
            raise QueryBotUnavailableError(
                "Bot en mantenimiento."
            )

        return bot

    # =====================================================
    # RESOLVER CMD
    # =====================================================

    async def resolve_command(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        bot_version: str,
        command: str,
    ) -> EffectiveCommand:

        normalized_command = (
            self._normalize_command(
                command
            )
        )

        version = (
            self._normalize_version(
                bot_version
            )
        )

        command_without_slash = (
            normalized_command
            .lstrip("/")
        )

        result = await session.execute(
            select(
                CommandModel
            ).where(
                func.lower(
                    CommandModel.command
                ).in_(
                    (
                        normalized_command,
                        command_without_slash,
                    )
                )
            )
        )

        command_model = (
            result.scalar_one_or_none()
        )

        if command_model is None:
            raise QueryCommandNotFoundError(
                "CMD no encontrado."
            )

        # =================================================
        # ESTADO GLOBAL + VERSIÓN
        # =================================================

        base_enabled = (
            command_model
            .effective_global_enabled(
                version
            )
        )

        config_result = await session.execute(
            select(
                BotCommandModel
            ).where(
                BotCommandModel.bot_id
                == bot_id,

                BotCommandModel.command_id
                == command_model.id,
            )
        )

        config = (
            config_result
            .scalar_one_or_none()
        )

        # =================================================
        # SIN OVERRIDE
        # =================================================

        if config is None:

            enabled = (
                base_enabled
            )

            try:
                price = max(
                    0,
                    int(
                        command_model.price
                    ),
                )

            except (
                TypeError,
                ValueError,
            ):
                price = 0

            level = (
                command_model
                .normalized_level
            )

            title = (
                command_model.title
            )

        # =================================================
        # CON OVERRIDE DEL BOT
        # =================================================

        else:

            enabled = (
                config.effective_enabled(
                    base_enabled
                )
            )

            price = (
                config.effective_price(
                    command_model.price
                )
            )

            level = (
                config.effective_level(
                    command_model.level
                )
            )

            title = (
                config.effective_title(
                    command_model.title
                )
            )

        if not enabled:
            raise QueryCommandDisabledError(
                "CMD no disponible para "
                "esta versión."
            )

        return EffectiveCommand(
            model=command_model,

            enabled=True,

            price=price,

            level=level,

            title=title,

            provider_key=(
                command_model.provider_key
            ),
        )

    # =====================================================
    # BUSCAR USUARIO
    # =====================================================

    async def _get_user(
        self,
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

    # =====================================================
    # LÍMITE DIARIO
    # =====================================================

    async def _check_daily_limit(
        self,
        session: AsyncSession,
        *,
        bot: BotModel,
    ) -> None:

        try:
            limit = int(
                bot.daily_query_limit
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):
            limit = 0

        if limit <= 0:
            raise QueryDailyLimitError(
                "Las consultas no están "
                "habilitadas para este bot."
            )

        now = datetime.now(
            timezone.utc
        )

        start_of_day = (
            now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        )

        result = await session.execute(
            select(
                func.count(
                    AuditModel.id
                )
            ).where(
                AuditModel.bot_id
                == bot.id,

                AuditModel.category
                == "QUERY",

                AuditModel.action
                == "QUERY_PROVIDER_CALL",

                AuditModel.created_at
                >= start_of_day,
            )
        )

        used = int(
            result.scalar_one()
            or 0
        )

        if used >= limit:
            raise QueryDailyLimitError(
                "El bot alcanzó su límite "
                "diario de consultas."
            )

    # =====================================================
    # RESOLVER RUTA AUTORIZADA
    # =====================================================

    @staticmethod
    def _resolve_route(
        provider_key: str | None,
    ) -> ProviderRoute:

        key = (
            str(
                provider_key
                or ""
            )
            .strip()
            .upper()
        )

        if not key:
            raise QueryProviderNotConfiguredError(
                "El CMD aún no tiene un "
                "servicio de proveedor configurado."
            )

        route = (
            AUTHORIZED_PROVIDER_ROUTES
            .get(
                key
            )
        )

        if route is None:
            raise QueryProviderNotConfiguredError(
                "Este CMD todavía no está "
                "conectado al proveedor autorizado."
            )

        return route

    # =====================================================
    # VALIDAR ARGUMENTO
    # =====================================================

    @staticmethod
    def _validate_argument(
        argument: str,
        route: ProviderRoute,
    ) -> str:

        value = (
            str(argument or "")
            .strip()
        )

        if len(value) < route.min_length:

            raise QueryInvalidInputError(
                "Faltan datos para realizar "
                "la consulta."
            )

        if len(value) > route.max_length:

            raise QueryInvalidInputError(
                "El dato ingresado excede "
                "el tamaño permitido."
            )

        if (
            not route.allow_spaces
            and any(
                character.isspace()
                for character
                in value
            )
        ):

            raise QueryInvalidInputError(
                "El dato ingresado contiene "
                "espacios no permitidos."
            )

        if (
            route.digits_only
            and not value.isdigit()
        ):

            raise QueryInvalidInputError(
                "El dato debe contener "
                "únicamente números."
            )

        # No aceptar caracteres de control.
        if any(
            ord(character) < 32
            for character
            in value
        ):

            raise QueryInvalidInputError(
                "El dato contiene caracteres "
                "no permitidos."
            )

        return value

    # =====================================================
    # COMPROBAR PROVEEDOR
    # =====================================================

    async def _check_provider_ready(
        self,
        session: AsyncSession,
    ) -> None:

        health = (
            await fuentesdata_service
            .healthcheck(
                session
            )
        )

        if not health.success:

            raise QueryProviderNotConfiguredError(
                "El servicio externo todavía "
                "no se encuentra disponible."
            )

    # =====================================================
    # PETICIÓN AL PROVEEDOR
    # =====================================================

    async def _provider_request(
        self,
        session: AsyncSession,
        *,
        route: ProviderRoute,
        argument: str,
    ) -> ProviderResult:

        method = (
            str(route.method)
            .strip()
            .upper()
        )

        if method == "GET":

            return await fuentesdata_service.get(
                route.endpoint,

                params={
                    route.argument_key:
                    argument
                },

                session=session,
            )

        if method == "POST":

            return await fuentesdata_service.post(
                route.endpoint,

                json_data={
                    route.argument_key:
                    argument
                },

                session=session,
            )

        raise QueryProviderNotConfiguredError(
            "Método del proveedor "
            "no autorizado."
        )

    # =====================================================
    # AUDITORÍA ERROR PROVEEDOR
    # =====================================================

    async def _audit_provider_error(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        telegram_id: int,
        username: str | None,
        role: str,
        command: str,
        argument: str,
        request_id: str | None,
        provider_result: ProviderResult,
        duration_ms: int,
    ) -> None:

        await audit_service.log(
            session,

            action="QUERY_PROVIDER_CALL",

            bot_id=bot_id,

            request_id=request_id,

            source="TELEGRAM",

            category="QUERY",

            actor_telegram_id=(
                telegram_id
            ),

            actor_username=(
                username
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

            success=False,

            status="ERROR",

            error_code=(
                str(
                    provider_result
                    .status_code
                )
            ),

            error_message=(
                provider_result.message
            ),

            credits_charged=0,

            duration_ms=(
                duration_ms
            ),
        )

    # =====================================================
    # EJECUTAR CONSULTA
    # =====================================================

    async def execute(
        self,
        session: AsyncSession,
        *,
        bot_id: int,
        bot_version: str,
        telegram_id: int,
        username: str | None,
        actor_role: str,
        command: str,
        argument: str,
        request_id: str | None = None,
    ) -> QueryExecutionResult:

        started = (
            perf_counter()
        )

        role = (
            self._normalize_role(
                actor_role
            )
        )

        # =================================================
        # BOT
        # =================================================

        bot = await self._get_bot(
            session,
            bot_id=bot_id,
        )

        # PostgreSQL es la autoridad para la versión.
        database_version = (
            self._normalize_version(
                bot.version
            )
        )

        # Se mantiene por compatibilidad con middleware.
        _ = bot_version

        # =================================================
        # CMD
        # =================================================

        effective = (
            await self.resolve_command(
                session,

                bot_id=bot_id,

                bot_version=(
                    database_version
                ),

                command=command,
            )
        )

        # =================================================
        # USUARIO
        # =================================================

        user = await self._get_user(
            session,

            bot_id=bot_id,

            telegram_id=telegram_id,
        )

        if (
            effective.model
            .requires_registration
            and user is None
        ):

            raise QueryAccountRequiredError(
                "Debes registrarte primero."
            )

        if user is not None:

            if (
                not user.is_registered
                or not user.is_active
                or user.is_banned
            ):

                raise QueryAccountBlockedError(
                    "La cuenta no está "
                    "habilitada."
                )

        # Créditos y estadísticas necesitan
        # un UserModel persistido.
        if user is None:

            raise QueryAccountRequiredError(
                "Se requiere una cuenta "
                "registrada."
            )

        # =================================================
        # PERMISOS
        # =================================================

        if (
            effective.model
            .requires_authorization
            and not has_permission(
                role,
                "use_queries",
            )
        ):

            raise QueryPermissionError(
                "No tienes autorización "
                "para realizar consultas."
            )

        # =================================================
        # LÍMITE DIARIO
        # =================================================

        await self._check_daily_limit(
            session,
            bot=bot,
        )

        # =================================================
        # RUTA AUTORIZADA
        # =================================================

        route = (
            self._resolve_route(
                effective.provider_key
            )
        )

        # =================================================
        # VALIDAR ENTRADA
        #
        # ERROR AQUÍ = NO API + NO COBRO
        # =================================================

        validated_argument = (
            self._validate_argument(
                argument,
                route,
            )
        )

        # =================================================
        # PROVEEDOR DISPONIBLE
        #
        # SE COMPRUEBA ANTES DE COBRAR
        # =================================================

        await self._check_provider_ready(
            session
        )

        # =================================================
        # SALDO
        # =================================================

        balance = int(
            user.credits
            or 0
        )

        if (
            effective.price > 0
            and balance
            < effective.price
        ):

            raise InsufficientCreditsError(
                "Créditos insuficientes."
            )

        # =================================================
        # COBRAR
        # =================================================

        charged = False

        if effective.price > 0:

            await credit_service.charge_query(
                session,

                bot_id=bot_id,

                user_id=user.id,

                cost=(
                    effective.price
                ),

                command=command,
            )

            charged = True

        # =================================================
        # LLAMAR PROVEEDOR
        # =================================================

        provider_result = (
            await self._provider_request(
                session,

                route=route,

                argument=(
                    validated_argument
                ),
            )
        )

        # =================================================
        # ERROR TÉCNICO
        #
        # SI HUBO COBRO → REEMBOLSO
        # =================================================

        if not provider_result.success:

            if (
                charged
                and effective.price > 0
            ):

                await credit_service.refund_query(
                    session,

                    bot_id=bot_id,

                    user_id=user.id,

                    amount=(
                        effective.price
                    ),

                    command=command,

                    reason=(
                        "Fallo técnico "
                        "del proveedor."
                    ),
                )

            duration_ms = int(
                (
                    perf_counter()
                    - started
                )
                * 1000
            )

            await self._audit_provider_error(
                session,

                bot_id=bot_id,

                telegram_id=(
                    telegram_id
                ),

                username=username,

                role=role,

                command=command,

                argument=(
                    validated_argument
                ),

                request_id=(
                    request_id
                ),

                provider_result=(
                    provider_result
                ),

                duration_ms=(
                    duration_ms
                ),
            )

            raise QueryProviderError(
                "El proveedor no pudo "
                "completar la consulta."
            )

        # =================================================
        # COSTO FINAL
        #
        # IMPORTANTE:
        #
        # Si la consulta fue válida y el proveedor
        # respondió correctamente, el costo se mantiene.
        #
        # Esto incluye:
        #
        # - resultados encontrados;
        # - Sin Resultados.
        # =================================================

        final_cost = (
            effective.price
        )

        # =================================================
        # ESTADÍSTICAS
        # =================================================

        await session.refresh(
            user
        )

        user.total_queries = (
            int(
                user.total_queries
                or 0
            )
            + 1
        )

        # Campo real existente en UserModel.
        user.last_query_at = (
            datetime.now(
                timezone.utc
            )
        )

        if provider_result.no_results:

            user.no_result_queries = (
                int(
                    user.no_result_queries
                    or 0
                )
                + 1
            )

        else:

            user.successful_queries = (
                int(
                    user.successful_queries
                    or 0
                )
                + 1
            )

        user.total_credits_spent = (
            int(
                user.total_credits_spent
                or 0
            )
            + int(
                final_cost
            )
        )

        await session.commit()

        # =================================================
        # SALDO FINAL
        # =================================================

        remaining_credits = (
            await credit_service.get_balance(
                session,

                bot_id=bot_id,

                user_id=user.id,
            )
        )

        duration_ms = int(
            (
                perf_counter()
                - started
            )
            * 1000
        )

        # =================================================
        # AUDITORÍA
        # =================================================

        await audit_service.log(
            session,

            action="QUERY_PROVIDER_CALL",

            bot_id=bot_id,

            request_id=request_id,

            source="TELEGRAM",

            category="QUERY",

            actor_telegram_id=(
                telegram_id
            ),

            actor_username=(
                username
            ),

            actor_role=(
                role
            ),

            command=(
                command
            ),

            argument=(
                validated_argument
            ),

            success=True,

            status=(
                "NO_RESULTS"
                if provider_result.no_results
                else "COMPLETED"
            ),

            credits_charged=(
                final_cost
            ),

            duration_ms=(
                duration_ms
            ),

            extra_data={
                "provider_status": (
                    provider_result
                    .status_code
                ),

                "no_results": (
                    provider_result
                    .no_results
                ),

                "command_code": (
                    effective.model.code
                ),

                "version": (
                    database_version
                ),
            },
        )

        return QueryExecutionResult(
            command=command,

            title=(
                effective.title
            ),

            level=(
                effective.level
            ),

            cost=(
                final_cost
            ),

            remaining_credits=(
                remaining_credits
            ),

            no_results=(
                provider_result
                .no_results
            ),

            provider_result=(
                provider_result
            ),

            duration_ms=(
                duration_ms
            ),
        )


query_engine = QueryEngine()
