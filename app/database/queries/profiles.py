from app.database.client import get_supabase
from typing import Dict, Any


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
