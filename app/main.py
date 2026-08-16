from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import close_db, init_db

# ============================================================
# IMPORTAR MODELOS
# ============================================================
#
# Estos imports hacen que SQLAlchemy conozca todos los modelos
# antes de ejecutar Base.metadata.create_all().
#
# Más adelante limpiaremos esto desde app/models/__init__.py.
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
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # --------------------------------------------------------
    # INICIO
    # --------------------------------------------------------

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

    # Crear/verificar tablas PostgreSQL
    await init_db()

    print(
        "[OK] Base de datos inicializada."
    )

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
        "=============================================="
    )
    print(
        " GUARDIAHEXBOT ONLINE"
    )
    print(
        "=============================================="
    )

    yield

    # --------------------------------------------------------
    # APAGADO
    # --------------------------------------------------------

    print(
        "=============================================="
    )
    print(
        " Cerrando GUARDIAHEXBOT..."
    )
    print(
        "=============================================="
    )

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
#
# El panel y la API funcionan desde el mismo dominio.
# Por seguridad no habilitamos orígenes externos todavía.
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
#
# Todos quedan debajo de:
#
# /api/...
#
# Ejemplos:
#
# /api/auth/...
# /api/bots/...
# /api/socios/...
# /api/commands/...
# /api/provider/...
#
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
# PÁGINA PRINCIPAL
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
        "login.html",
        {
            "request": request,
        },
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
        "master/dashboard.html",
        {
            "request": request,
        },
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
        "master/socios.html",
        {
            "request": request,
        },
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
        "master/bots.html",
        {
            "request": request,
        },
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
        "master/versions.html",
        {
            "request": request,
        },
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
        "master/commands.html",
        {
            "request": request,
        },
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
        "master/api.html",
        {
            "request": request,
        },
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
        "partner/panel.html",
        {
            "request": request,
        },
    )


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health",
    tags=["Sistema"],
)
async def health():

    return {
        "status": "ok",
        "service": "guardiahex-platform",
        "version": "1.0.0",
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
            "app": "GUARDIAHEXBOT",
            "platform": (
                "GUARDIAHEXBOT PLATFORM"
            ),
            "version": "1.0.0",
            "status": "online",
            "database": "postgresql",
            "realtime": True,
            "multi_bot": True,
        }
    )
