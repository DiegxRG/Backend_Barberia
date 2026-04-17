from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.dependencies import require_role
from app.models.calendar import CalendarStatusResponse, CalendarCallbackResponse
from app.services.calendar_service import calendar_service

router = APIRouter()


@router.get("/connect", summary="Iniciar OAuth con Google Calendar")
def connect_google_calendar(current_user: dict = Depends(require_role("admin", "barbero"))):
    auth_url = calendar_service.get_connect_url(current_user)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback", response_model=CalendarCallbackResponse, summary="Callback OAuth de Google")
def google_callback(code: str = Query(...), state: str = Query(...)):
    return calendar_service.handle_callback(code, state)


@router.get("/status", response_model=CalendarStatusResponse, summary="Estado de conexion a Google Calendar")
def calendar_status(current_user: dict = Depends(require_role("admin", "barbero"))):
    return calendar_service.get_status(current_user)


@router.delete("/disconnect", response_model=CalendarStatusResponse, summary="Desconectar Google Calendar")
def disconnect_calendar(current_user: dict = Depends(require_role("admin", "barbero"))):
    return calendar_service.disconnect(current_user)
