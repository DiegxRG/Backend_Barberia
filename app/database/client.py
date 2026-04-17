"""
Cliente Supabase singleton.
Reutiliza una única instancia de conexión en toda la aplicación.
"""

from supabase import create_client, Client
from app.config import settings

# ── Cliente singleton ────────────────────────────────────────
_client: Client | None = None


def get_supabase() -> Client:
    """
    Retorna cliente Supabase con SERVICE_ROLE_KEY.

    ⚠️ SERVICE_ROLE_KEY bypasea RLS (Row Level Security).
    Usar SOLO en el backend, nunca exponer al frontend.
    El backend es responsable de validar permisos via RBAC (dependencies.py).
    """
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _client
