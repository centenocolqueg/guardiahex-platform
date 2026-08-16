from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import settings
from app.database import (
    AsyncSessionLocal,
    close_db,
    init_db,
)

# ============================================================
# MODELOS
# ============================================================

from app.models import audit as audit_model  # noqa: F401
from app.models import bot as bot_model  # noqa: F401
from app.models import command as command_model  # noqa: F401
from app.models import plan as plan_model  # noqa: F401
from app.models import role as role_model  # noqa: F401
from app.models import settings as settings_model  # noqa: F401
from app.models import socio as socio_model  # noqa: F401
from app.models import transaction as transaction_model  # noqa: F401
from app.models import user as user_model  # noqa: F401

from app.models.bot import BotModel


# ============================================================
# SERVICIOS
# ============================================================

from app.bots.manager import bot_manager
from app.services.bot_runtime import bot_runtime_service
from app.services.catalog_sync import catalog_sync_service


# ============================================================
# API ROUTERS
# ============================================================

from app.api import auth as auth_api
from app.api import bots as bots_api
from app.api import commands as commands_api
from app.api import credits as credits_api
from app.api import dashboard as dashboard_api
from app.api import provider as provider_api
from app.api import realtime as realtime_api
from app.api import socios as socios_api
from app.api import statistics as statistics_api
from app.api import versions as versions_api


# ============================================================
# DIRECTORIOS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ============================================================
# SINCRONIZAR CATÁLOGO
# ============================================================

async def synchronize_command_catalog() -> None:
    """
    Sincroniza catalog.py con PostgreSQL.

    Debe ejecutarse antes de arrancar los bots,
    ya que query_engine consulta CommandModel
    directamente desde la base de datos.

    La sincronización es idempotente:
    reiniciar el servidor no duplica CMD.
    """

    async with AsyncSessionLocal() as session:

        result = await catalog_sync_service.sync(
            session
        )

        print(
            "[OK] Catálogo CMD sincronizado."
        )

        print(
            f"[INFO] CMD catálogo: {result.total}"
        )

        print(
            f"[INFO] CMD creados: {result.created}"
        )

        print(
            f"[INFO] CMD actualizados: {result.updated}"
        )

        print(
            f"[INFO] CMD sin cambios: {result.unchanged}"
        )


# ============================================================
# RESTAURAR BOTS ACTIVOS
# ============================================================

async def restore_enabled_bots() -> tuple[int, int]:
    """
    Busca en PostgreSQL los bots que estaban
    habilitados antes del reinicio del servidor
    e intenta volver a iniciar su polling.

    Un fallo individual no impide que los demás
    bots ni FastAPI continúen funcionando.
    """

    started = 0
    failed = 0

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(
                BotModel.id
            )
            .where(
                BotModel.enabled.is_(True)
            )
            .order_by(
                BotModel.id.asc()
            )
        )

        bot_ids = list(
            result.scalars().all()
        )

        if not bot_ids:

            print(
                "[INFO] No hay bots habilitados "
                "para restaurar."
            )

            return (
                started,
                failed,
            )

        print(
            f"[INFO] Restaurando "
            f"{len(bot_ids)} bot(s)..."
        )

        for bot_id in bot_ids:

            try:

                await bot_runtime_service.start(
                    session,
                    bot_id=bot_id,
                )

                started += 1

                print(
                    f"[OK] Bot ID {bot_id} ONLINE."
                )

            except Exception as exc:

                failed += 1

                # Nunca mostrar tokens ni secretos.
                print(
                    f"[ERROR] Bot ID {bot_id} "
                    f"no pudo iniciar: "
                    f"{type(exc).__name__}"
                )

    return (
        started,
        failed,
    )


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):

    print(
        "=============================================="
    )
    print(
        " GUARDIAHEXBOT PLATFORM"
    )
    print(
        " Iniciando sistema..."
    )
    print(
        "=============================================="
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    await init_db()

    print(
        "[OK] Base de datos inicializada."
    )

    # --------------------------------------------------------
    # CATÁLOGO 72 CMD
    # --------------------------------------------------------

    try:

        await synchronize_command_catalog()

    except Exception as exc:

        print(
            "[FATAL] No fue posible sincronizar "
            "el catálogo de comandos: "
            f"{type(exc).__name__}"
        )

        # Sin catálogo válido, los CMD dinámicos
        # no deben arrancar en un estado inconsistente.
        await close_db()

        raise

    # --------------------------------------------------------
    # RESTAURAR BOTS
    # --------------------------------------------------------

    started = 0
    failed = 0

    try:

        (
            started,
            failed,
        ) = await restore_enabled_bots()

    except Exception as exc:

        # FastAPI y el panel pueden seguir
        # funcionando aunque falle la
        # restauración global de Telegram.
        print(
            "[ERROR] No fue posible ejecutar "
            "la restauración automática de bots: "
            f"{type(exc).__name__}"
        )

    # --------------------------------------------------------
    # SISTEMA LISTO
    # --------------------------------------------------------

    print(
        "[OK] API preparada."
    )

    print(
        "[OK] Panel web preparado."
    )

    print(
        "[OK] Sistema realtime preparado."
    )

    print(
        f"[INFO] Bots ONLINE restaurados: "
        f"{started}"
    )

    if failed:

        print(
            f"[WARN] Bots que no pudieron iniciar: "
            f"{failed}"
        )

    print(
        "=============================================="
    )
    print(
        " GUARDIAHEXBOT ONLINE"
    )
    print(
        "=============================================="
    )

    try:

        yield

    finally:

        # ----------------------------------------------------
        # APAGADO
        # ----------------------------------------------------

        print(
            "=============================================="
        )
        print(
            " Cerrando GUARDIAHEXBOT..."
        )
        print(
            "=============================================="
        )

        # Primero detener Telegram/Aiogram.
        try:

            await bot_runtime_service.shutdown_all()

            print(
                "[OK] Bots Telegram detenidos."
            )

        except Exception as exc:

            print(
                "[WARN] Error cerrando runtimes: "
                f"{type(exc).__name__}"
            )

        # Después cerrar PostgreSQL.
        await close_db()

        print(
            "[OK] Base de datos desconectada."
        )

        print(
            "[OK] Sistema cerrado correctamente."
        )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="GUARDIAHEXBOT PLATFORM",
    description=(
        "Plataforma multi-bot de Telegram con "
        "panel maestro SUPERADMIN, bots de socios, "
        "créditos, roles, estadísticas, auditoría, "
        "versiones V1-V5 y administración centralizada."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=["*"],
)


# ============================================================
# STATIC
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR)
    ),
    name="static",
)


# ============================================================
# API ROUTERS
# ============================================================

app.include_router(
    auth_api.router,
    prefix="/api",
)

app.include_router(
    dashboard_api.router,
    prefix="/api",
)

app.include_router(
    socios_api.router,
    prefix="/api",
)

app.include_router(
    bots_api.router,
    prefix="/api",
)

app.include_router(
    versions_api.router,
    prefix="/api",
)

app.include_router(
    commands_api.router,
    prefix="/api",
)

app.include_router(
    credits_api.router,
    prefix="/api",
)

app.include_router(
    statistics_api.router,
    prefix="/api",
)

app.include_router(
    provider_api.router,
    prefix="/api",
)

app.include_router(
    realtime_api.router,
    prefix="/api",
)


# ============================================================
# ROOT
# ============================================================

@app.get(
    "/",
    include_in_schema=False,
)
async def root():

    return RedirectResponse(
        url="/login",
        status_code=302,
    )


# ============================================================
# LOGIN
# ============================================================

@app.get(
    "/login",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def login_page(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={},
    )


# ============================================================
# PANEL MASTER
# ============================================================

@app.get(
    "/master",
    include_in_schema=False,
)
async def master_root():

    return RedirectResponse(
        url="/master/dashboard",
        status_code=302,
    )


@app.get(
    "/master/dashboard",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def master_dashboard(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="master/dashboard.html",
        context={},
    )


@app.get(
    "/master/socios",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def master_socios(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="master/socios.html",
        context={},
    )


@app.get(
    "/master/bots",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def master_bots(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="master/bots.html",
        context={},
    )


@app.get(
    "/master/versions",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def master_versions(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="master/versions.html",
        context={},
    )


@app.get(
    "/master/commands",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def master_commands(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="master/commands.html",
        context={},
    )


@app.get(
    "/master/api",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def master_api(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="master/api.html",
        context={},
    )


# ============================================================
# PANEL SOCIO
# ============================================================

@app.get(
    "/partner",
    include_in_schema=False,
)
async def partner_root():

    return RedirectResponse(
        url="/partner/panel",
        status_code=302,
    )


@app.get(
    "/partner/panel",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def partner_panel(
    request: Request,
):

    return templates.TemplateResponse(
        request=request,
        name="partner/panel.html",
        context={},
    )


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health",
    tags=["Sistema"],
)
async def health():

    managed_bots = (
        bot_manager.all()
    )

    online_bots = sum(
        1
        for managed in managed_bots
        if bot_manager.status(
            managed.bot_id
        )
        == "ONLINE"
    )

    return {
        "status": "ok",
        "service": (
            "guardiahex-platform"
        ),
        "version": "1.0.0",
        "bots_loaded": len(
            managed_bots
        ),
        "bots_online": (
            online_bots
        ),
    }


# ============================================================
# INFORMACIÓN API
# ============================================================

@app.get(
    "/api/system/info",
    tags=["Sistema"],
)
async def system_info():

    return JSONResponse(
        {
            "app": (
                settings.app_name
            ),
            "platform": (
                "GUARDIAHEXBOT PLATFORM"
            ),
            "version": "1.0.0",
            "status": "online",
            "environment": (
                settings.app_env
            ),
            "database": (
                "postgresql"
            ),
            "realtime": (
                settings.websocket_enabled
            ),
            "multi_bot": True,
        }
    )
