from typing import List, Optional
from uuid import UUID
from app.database.client import get_supabase
from app.utils.errors import NotFoundError, InternalError as DatabaseError

def list_services(include_inactive: bool = False) -> List[dict]:
    sb = get_supabase()
    query = sb.table("services").select("*")
    if not include_inactive:
        query = query.eq("active", True)
    query = query.order("category").order("name")
    try:
        response = query.execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al listar servicios: {str(e)}")

def get_service_by_id(service_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("services").select("*").eq("id", str(service_id)).execute()
        if not response.data:
            return None
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al obtener servicio: {str(e)}")

def create_service(data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("services").insert(data).execute()
        if not response.data:
            raise DatabaseError("No se pudo crear el servicio (no devolvió datos).")
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al crear servicio: {str(e)}")

def update_service(service_id: UUID, data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("services").update(data).eq("id", str(service_id)).execute()
        if not response.data:
            raise NotFoundError("Servicio no encontrado")
        return response.data[0]
    except NotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(f"Error al actualizar servicio: {str(e)}")

def update_service_status(service_id: UUID, active: bool) -> dict:
    return update_service(service_id, {"active": active})
