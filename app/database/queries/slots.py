from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from app.database.client import get_supabase
from app.utils.errors import InternalError as DatabaseError


def get_service_by_id(service_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("services").select("*").eq("id", str(service_id)).execute()
        if not response.data:
            return None
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al obtener servicio para slots: {str(e)}")


def get_barber_by_id(barber_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("barbers").select("*").eq("id", str(barber_id)).execute()
        if not response.data:
            return None
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al obtener barbero para slots: {str(e)}")


def get_availability_rule(barber_id: UUID, day_of_week: int) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = (
            sb.table("availability_rules")
            .select("*")
            .eq("barber_id", str(barber_id))
            .eq("day_of_week", day_of_week)
            .eq("active", True)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al obtener regla de disponibilidad: {str(e)}")


def get_breaks_for_day(barber_id: UUID, day_of_week: int) -> List[dict]:
    sb = get_supabase()
    try:
        response = (
            sb.table("breaks")
            .select("*")
            .eq("barber_id", str(barber_id))
            .eq("day_of_week", day_of_week)
            .eq("active", True)
            .order("start_time")
            .execute()
        )
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al obtener breaks del dia: {str(e)}")


def is_day_off(barber_id: UUID, target_date: date) -> bool:
    sb = get_supabase()
    try:
        response = (
            sb.table("day_off")
            .select("id")
            .eq("barber_id", str(barber_id))
            .eq("date", target_date.isoformat())
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception as e:
        raise DatabaseError(f"Error al verificar day off: {str(e)}")


def get_active_bookings(barber_id: UUID, day_start_utc: datetime, day_end_utc: datetime) -> List[dict]:
    sb = get_supabase()
    try:
        response = (
            sb.table("bookings")
            .select("id,start_at,end_at,status")
            .eq("barber_id", str(barber_id))
            .in_("status", ["pending", "confirmed"])
            .lt("start_at", day_end_utc.isoformat())
            .gt("end_at", day_start_utc.isoformat())
            .order("start_at")
            .execute()
        )
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al obtener bookings activas: {str(e)}")
