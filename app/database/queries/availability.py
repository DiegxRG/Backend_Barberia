from typing import List, Optional
from uuid import UUID
from datetime import date
from app.database.client import get_supabase
from app.utils.errors import InternalError as DatabaseError

# --- RULES ---
def get_rules(barber_id: UUID) -> List[dict]:
    sb = get_supabase()
    try:
        response = sb.table("availability_rules").select("*").eq("barber_id", str(barber_id)).execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al obtener reglas availability: {str(e)}")

def delete_all_rules(barber_id: UUID) -> None:
    sb = get_supabase()
    try:
        sb.table("availability_rules").delete().eq("barber_id", str(barber_id)).execute()
    except Exception as e:
        raise DatabaseError(f"Error al eliminar reglas: {str(e)}")

def bulk_insert_rules(data: List[dict]) -> List[dict]:
    sb = get_supabase()
    try:
        if not data:
            return []
        response = sb.table("availability_rules").insert(data).execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al insertar reglas: {str(e)}")

# --- BREAKS ---
def get_breaks(barber_id: UUID) -> List[dict]:
    sb = get_supabase()
    try:
        response = sb.table("breaks").select("*").eq("barber_id", str(barber_id)).execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al obtener breaks: {str(e)}")

def create_break(data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("breaks").insert(data).execute()
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al crear break: {str(e)}")

def delete_break(break_id: UUID) -> None:
    sb = get_supabase()
    try:
        sb.table("breaks").delete().eq("id", str(break_id)).execute()
    except Exception as e:
        raise DatabaseError(f"Error al eliminar break: {str(e)}")

# --- DAYS OFF ---
def get_days_off(barber_id: UUID, from_date: Optional[date] = None) -> List[dict]:
    sb = get_supabase()
    try:
        query = sb.table("day_off").select("*").eq("barber_id", str(barber_id))
        if from_date:
            query = query.gte("date", from_date.isoformat())
        query = query.order("date")
        response = query.execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al obtener days off: {str(e)}")

def create_day_off(data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("day_off").insert(data).execute()
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al crear day off: {str(e)}")

def delete_day_off(barber_id: UUID, target_date: date) -> None:
    sb = get_supabase()
    try:
        sb.table("day_off").delete().eq("barber_id", str(barber_id)).eq("date", target_date.isoformat()).execute()
    except Exception as e:
        raise DatabaseError(f"Error al eliminar day off: {str(e)}")
