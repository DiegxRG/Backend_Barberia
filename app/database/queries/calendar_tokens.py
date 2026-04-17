from datetime import datetime

from app.database.client import get_supabase
from app.utils.errors import InternalError as DatabaseError


def get_token_by_user(user_id: str) -> dict | None:
    sb = get_supabase()
    try:
        response = (
            sb.table("google_calendar_tokens")
            .select("*")
            .eq("user_id", user_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception as e:
        raise DatabaseError(f"Error al obtener token de calendar: {str(e)}")


def upsert_token(
    user_id: str,
    access_token: str,
    refresh_token: str,
    token_expires_at: datetime,
    calendar_id: str = "primary",
) -> dict:
    sb = get_supabase()
    payload = {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": token_expires_at.isoformat(),
        "calendar_id": calendar_id,
        "active": True,
    }
    try:
        response = sb.table("google_calendar_tokens").upsert(payload, on_conflict="user_id").execute()
        if not response.data:
            raise DatabaseError("No se pudo guardar token de calendar")
        return response.data[0]
    except Exception as e:
        raise DatabaseError(f"Error al guardar token de calendar: {str(e)}")


def deactivate_token(user_id: str) -> None:
    sb = get_supabase()
    try:
        sb.table("google_calendar_tokens").update({"active": False}).eq("user_id", user_id).execute()
    except Exception as e:
        raise DatabaseError(f"Error al desconectar calendar: {str(e)}")
