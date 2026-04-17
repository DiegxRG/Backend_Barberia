"""
Configuración centralizada del proyecto.
Usa pydantic-settings para cargar variables desde .env con validación de tipos.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración del backend cargada desde variables de entorno."""

    # ── Supabase ──────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str = "PENDIENTE"

    # ── App ───────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173"

    # ── Google Calendar OAuth ─────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/calendar/callback"
    GOOGLE_SCOPES: str = "https://www.googleapis.com/auth/calendar.events"
    GOOGLE_CALENDAR_ENABLED: bool = False  # Feature flag
    TOKEN_ENCRYPTION_KEY: str = ""

    # ── Negocio ───────────────────────────────────────────────
    BUSINESS_TIMEZONE: str = "America/Lima"
    MIN_BOOKING_ADVANCE_MINUTES: int = 30
    MAX_BOOKING_ADVANCE_DAYS: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Singleton cacheado de Settings. Evita releer .env en cada request."""
    return Settings()


settings = get_settings()
