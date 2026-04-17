"""
Punto de entrada de la aplicación FastAPI.
Configura CORS, exception handlers y registra todos los routers.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

from app.config import settings
from app.utils.errors import AppException


# ── Lifespan (startup/shutdown) ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de inicio y cierre de la aplicación."""
    print(f"[*] Barberia API iniciando en modo: {settings.APP_ENV}")
    print(f"[*] Zona horaria del negocio: {settings.BUSINESS_TIMEZONE}")
    print(f"[*] Google Calendar: {'Habilitado' if settings.GOOGLE_CALENDAR_ENABLED else 'Deshabilitado'}")
    yield
    print("[*] Barberia API cerrando...")


# ── App ──────────────────────────────────────────────────────
app = FastAPI(
    title="Barbería API",
    description="Sistema de Reservas para Barbería - Backend REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ──────────────────────────────────────
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Manejo centralizado de errores de la aplicación."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": exc.code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# ── Health Check ─────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de salud para monitoreo."""
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ── Routers ──────────────────────────────────────────────────
# Se registran conforme se implementan en cada fase.
# Fase 1.3:
from app.routers.auth import router as auth_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])

# Fase 1.5:
from app.routers.services import router as services_router
app.include_router(services_router, prefix="/api/v1/services", tags=["Servicios"])

# Fase 1.6:
from app.routers.barbers import router as barbers_router
app.include_router(barbers_router, prefix="/api/v1/barbers", tags=["Barberos"])

# Fase 2.1:
from app.routers.availability import router as availability_router
app.include_router(availability_router, prefix="/api/v1", tags=["Disponibilidad"])

# Fase 2.2:
from app.routers.slots import router as slots_router
app.include_router(slots_router, prefix="/api/v1/slots", tags=["Slots"])

# Fase 2.3:
from app.routers.bookings import router as bookings_router
app.include_router(bookings_router, prefix="/api/v1/bookings", tags=["Reservas"])

# Fase 3.1:
from app.routers.calendar import router as calendar_router
app.include_router(calendar_router, prefix="/api/v1/calendar", tags=["Google Calendar"])

# Fase 3.3:
# from app.routers.dashboard import router as dashboard_router
# app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
