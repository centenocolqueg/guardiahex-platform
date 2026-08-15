from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Aquí iniciaremos posteriormente:
    # - Base de datos
    # - GUARDIAHEXBOT
    # - Bot Manager
    # - WebSockets
    # - Servicios en tiempo real
    yield

    # Aquí cerraremos conexiones y procesos
    # de forma segura al apagar el sistema.


app = FastAPI(
    title="GUARDIAHEXBOT PLATFORM",
    description=(
        "Plataforma multi-bot con panel maestro, "
        "bots de socios, créditos, roles, estadísticas "
        "y administración centralizada."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.get("/", tags=["Sistema"])
async def root():
    return JSONResponse(
        {
            "app": "GUARDIAHEXBOT",
            "version": "1.0.0",
            "status": "online",
            "message": "GUARDIAHEXBOT PLATFORM funcionando correctamente.",
        }
    )


@app.get("/health", tags=["Sistema"])
async def health():
    return {
        "status": "ok",
        "service": "guardiahex-platform",
    }
