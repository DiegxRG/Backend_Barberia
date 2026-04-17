"""
Dependencias de autenticación para FastAPI.
Verifica JWT de Supabase y extrae datos del usuario.

Uso en routers:
    @router.get("/ruta")
    async def endpoint(user = Depends(get_current_user)):
        ...

    @router.post("/ruta-admin")
    async def endpoint(user = Depends(require_role("admin"))):
        ...
"""

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings
from app.database.client import get_supabase
from app.utils.errors import UnauthorizedError, ForbiddenError


# ── Bearer Token Scheme ──────────────────────────────────────
security = HTTPBearer(
    scheme_name="Supabase JWT",
    description="Token JWT obtenido de Supabase Auth"
)

optional_security = HTTPBearer(
    auto_error=False,
    scheme_name="Supabase JWT Optional",
    description="Token JWT opcional para permisos avanzados"
)


def _resolve_user_from_token(token: str) -> dict:
    """Decodifica token JWT de Supabase y retorna el perfil activo del usuario."""
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expirado. Inicia sesión nuevamente.")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Token inválido.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token no contiene identificador de usuario.")

    supabase = get_supabase()
    result = supabase.table("profiles").select("*").eq("id", user_id).execute()

    if not result.data:
        raise UnauthorizedError("Perfil de usuario no encontrado.")

    profile = result.data[0]
    if not profile.get("active", True):
        raise UnauthorizedError("Cuenta de usuario desactivada.")

    return profile


# ── Obtener usuario autenticado ──────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verifica el JWT de Supabase y retorna el perfil del usuario.

    Flujo:
    1. Extrae token del header Authorization: Bearer <token>
    2. Decodifica y verifica con SUPABASE_JWT_SECRET
    3. Extrae user_id (sub) del payload
    4. Consulta perfil en tabla 'profiles'
    5. Retorna dict con id, full_name, email, role, etc.

    Raises:
        UnauthorizedError: Si el token es inválido o expirado
    """
    return _resolve_user_from_token(credentials.credentials)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security)
) -> dict | None:
    """
    Retorna usuario autenticado si se envía token válido, o None si no se envía token.
    """
    if credentials is None:
        return None
    return _resolve_user_from_token(credentials.credentials)


# ── Verificar rol del usuario ────────────────────────────────
def require_role(*roles: str):
    """
    Dependency factory que verifica que el usuario tenga uno de los roles permitidos.

    Uso:
        @router.post("/admin-only")
        async def endpoint(user = Depends(require_role("admin"))):
            ...

        @router.patch("/barbero-o-admin")
        async def endpoint(user = Depends(require_role("admin", "barbero"))):
            ...

    Args:
        *roles: Roles permitidos (ej: "admin", "barbero", "cliente")

    Returns:
        Dependency function que retorna el perfil del usuario si tiene el rol correcto.

    Raises:
        ForbiddenError: Si el usuario no tiene ninguno de los roles requeridos.
    """
    async def role_checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "cliente")
        if user_role not in roles:
            raise ForbiddenError(
                f"Se requiere rol {' o '.join(roles)}. Tu rol actual: {user_role}"
            )
        return user

    return role_checker
