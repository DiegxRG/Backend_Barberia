from datetime import datetime
from typing import Optional, List
from uuid import UUID

from app.database.client import get_supabase
from app.utils.errors import InternalError as DatabaseError


def get_service_by_id(service_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("services").select("*").eq("id", str(service_id)).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise DatabaseError(f"Error al obtener servicio: {str(e)}")


def get_barber_by_id(barber_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("barbers").select("*").eq("id", str(barber_id)).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise DatabaseError(f"Error al obtener barbero: {str(e)}")


def get_barber_by_user_id(user_id: str) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("barbers").select("*").eq("user_id", user_id).eq("active", True).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise DatabaseError(f"Error al obtener barbero por usuario: {str(e)}")


def barber_offers_service(barber_id: UUID, service_id: UUID) -> bool:
    sb = get_supabase()
    try:
        response = (
            sb.table("barber_services")
            .select("id")
            .eq("barber_id", str(barber_id))
            .eq("service_id", str(service_id))
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception as e:
        raise DatabaseError(f"Error al validar servicio del barbero: {str(e)}")


def get_booking_by_id(booking_id: UUID) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("bookings").select("*").eq("id", str(booking_id)).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise DatabaseError(f"Error al obtener booking: {str(e)}")


def get_booking_by_idempotency(idempotency_key: str) -> Optional[dict]:
    sb = get_supabase()
    try:
        response = sb.table("bookings").select("*").eq("idempotency_key", idempotency_key).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise DatabaseError(f"Error al buscar idempotency key: {str(e)}")


def create_booking(data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("bookings").insert(data).execute()
        if not response.data:
            raise DatabaseError("No se pudo crear la reserva")
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al crear booking: {str(e)}")


def update_booking(booking_id: UUID, data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("bookings").update(data).eq("id", str(booking_id)).execute()
        if not response.data:
            raise DatabaseError("No se pudo actualizar la reserva")
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al actualizar booking: {str(e)}")


def get_overlapping_bookings(barber_id: UUID, start_at: datetime, end_at: datetime) -> List[dict]:
    sb = get_supabase()
    try:
        response = (
            sb.table("bookings")
            .select("id,start_at,end_at,status")
            .eq("barber_id", str(barber_id))
            .in_("status", ["pending", "confirmed"])
            .lt("start_at", end_at.isoformat())
            .gt("end_at", start_at.isoformat())
            .execute()
        )
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al validar solapamiento: {str(e)}")


def list_bookings(
    *,
    client_user_id: Optional[str] = None,
    barber_id: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> List[dict]:
    sb = get_supabase()
    try:
        query = (
            sb.table("bookings")
            .select("*")
            .order("start_at", desc=False)
            .range(offset, offset + limit - 1)
        )

        if client_user_id:
            query = query.eq("client_user_id", client_user_id)
        if barber_id:
            query = query.eq("barber_id", barber_id)
        if status:
            query = query.eq("status", status)
        if from_date:
            query = query.gte("start_at", from_date)
        if to_date:
            query = query.lte("start_at", to_date)

        response = query.execute()
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al listar bookings: {str(e)}")


def create_booking_history(data: dict) -> dict:
    sb = get_supabase()
    try:
        response = sb.table("booking_history").insert(data).execute()
        if not response.data:
            raise DatabaseError("No se pudo crear historial")
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al crear historial de booking: {str(e)}")


def get_booking_history(booking_id: UUID) -> List[dict]:
    sb = get_supabase()
    try:
        response = (
            sb.table("booking_history")
            .select("*")
            .eq("booking_id", str(booking_id))
            .order("created_at", desc=False)
            .execute()
        )
        return response.data
    except Exception as e:
        raise DatabaseError(f"Error al obtener historial: {str(e)}")
