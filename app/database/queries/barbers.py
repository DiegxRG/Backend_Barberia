from typing import List, Optional
from uuid import UUID
from app.database.client import get_supabase
from app.utils.errors import NotFoundError, InternalError as DatabaseError

def list_barbers(include_inactive: bool = False) -> List[dict]:
    sb = get_supabase()
    query = sb.table("barbers").select("*")
    if not include_inactive:
        query = query.eq("active", True)
    query = query.order("full_name")
    
    try:
        response = query.execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al listar barberos: {str(e)}")

def get_barber_by_id(barber_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("barbers").select("*").eq("id", str(barber_id)).execute()
        if not response.data:
            return None
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al obtener barbero: {str(e)}")


def get_barber_by_user_id(user_id: str, include_inactive: bool = True) -> Optional[dict]:
    sb = get_supabase()
    try:
        query = sb.table("barbers").select("*").eq("user_id", user_id)
        if not include_inactive:
            query = query.eq("active", True)
        response = query.limit(1).execute()
        if not response.data:
            return None
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al obtener barbero por user_id: {str(e)}")

def create_barber(data: dict) -> dict:
    sb = get_supabase()
    if 'user_id' in data and data['user_id'] is not None:
        data['user_id'] = str(data['user_id'])
    
    try:
        response = sb.table("barbers").insert(data).execute()
        if not response.data:
            raise DatabaseError("No se pudo crear el barbero (no devolvió datos).")
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al crear barbero: {str(e)}")

def update_barber(barber_id: UUID, data: dict) -> dict:
    sb = get_supabase()
    if 'user_id' in data and data['user_id'] is not None:
        data['user_id'] = str(data['user_id'])
        
    try:
        response = sb.table("barbers").update(data).eq("id", str(barber_id)).execute()
        if not response.data:
            raise NotFoundError("Barbero no encontrado")
        return response.data[0]
    except NotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(f"Error al actualizar barbero: {str(e)}")

def update_barber_status(barber_id: UUID, active: bool) -> dict:
    return update_barber(barber_id, {"active": active})

# -- Barber Services --

def assign_services_to_barber(barber_id: UUID, service_ids: List[UUID]) -> None:
    sb = get_supabase()
    
    # 1. Eliminar asignaciones previas
    sb.table("barber_services").delete().eq("barber_id", str(barber_id)).execute()
    
    # 2. Insertar nuevas
    if service_ids:
        inserts = [{"barber_id": str(barber_id), "service_id": str(sid)} for sid in service_ids]
        sb.table("barber_services").insert(inserts).execute()

def get_barber_services(barber_id: UUID) -> List[dict]:
    sb = get_supabase()
    try:
        response = sb.table("barber_services").select("services(*)").eq("barber_id", str(barber_id)).execute()
        services = []
        for item in response.data:
            if "services" in item and item["services"]:
                # Manejar caso de que devuelva una lista o auth dict
                svc = item["services"]
                if isinstance(svc, list) and len(svc) > 0:
                    services.append(svc[0])
                elif isinstance(svc, dict):
                    services.append(svc)
        return services
    except Exception as e:
        raise DatabaseError(f"Error al obtener servicios asignados: {str(e)}")

def get_barbers_by_service(service_id: UUID) -> List[dict]:
    """Retorna todos los barberos activos que ofrecen un servicio dado."""
    sb = get_supabase()
    try:
        response = (
            sb.table("barber_services")
            .select("barbers(*)")
            .eq("service_id", str(service_id))
            .execute()
        )
        barbers = []
        for item in response.data:
            if "barbers" in item and item["barbers"]:
                barber = item["barbers"]
                if isinstance(barber, list) and len(barber) > 0:
                    barber = barber[0]
                if isinstance(barber, dict) and barber.get("active", False):
                    barbers.append(barber)
        return barbers
    except Exception as e:
        raise DatabaseError(f"Error al obtener barberos por servicio: {str(e)}")
