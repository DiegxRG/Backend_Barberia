from app.database.client import get_supabase
from typing import Dict, Any, List, Optional


def get_profile(user_id: str) -> Dict[str, Any] | None:
    """Busca y retorna un perfil por ID."""
    supabase = get_supabase()
    result = supabase.table("profiles").select("*").eq("id", user_id).execute()
    
    if not result.data:
        return None
    return result.data[0]


def update_profile(user_id: str, data: Dict[str, Any]) -> Dict[str, Any] | None:
    """Actualiza el perfil de un usuario y retorna los datos actualizados."""
    supabase = get_supabase()
    
    if not data:
        return get_profile(user_id)
        
    result = supabase.table("profiles").update(data).eq("id", user_id).execute()
    
    if not result.data:
        return None
    return result.data[0]


def update_profile_role(user_id: str, role: str) -> Dict[str, Any] | None:
    """Actualiza el rol del perfil y retorna el perfil actualizado."""
    supabase = get_supabase()
    result = supabase.table("profiles").update({"role": role}).eq("id", user_id).execute()
    if not result.data:
        return None
    return result.data[0]


def list_profiles(
    role: Optional[str] = None,
    active: Optional[bool] = None,
    *,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Lista perfiles con filtros opcionales."""
    supabase = get_supabase()
    query = (
        supabase.table("profiles")
        .select("*")
        .order("full_name")
        .range(offset, offset + limit - 1)
    )

    if role is not None:
        query = query.eq("role", role)
    if active is not None:
        query = query.eq("active", active)

    result = query.execute()
    return result.data or []
