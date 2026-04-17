from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_user, require_role
from app.models.booking import (
    BookingCreate,
    BookingResponse,
    BookingCancel,
    BookingReschedule,
    BookingHistoryResponse,
)
from app.services.booking_service import booking_service

router = APIRouter()


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, summary="Crear reserva")
def create_booking(payload: BookingCreate, current_user: dict = Depends(require_role("cliente", "admin"))):
    return booking_service.create_booking(payload, current_user)


@router.get("", response_model=List[BookingResponse], summary="Listar reservas")
def list_bookings(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
):
    return booking_service.list_bookings(
        current_user=current_user,
        status=status_filter,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/{booking_id}", response_model=BookingResponse, summary="Obtener reserva por ID")
def get_booking(booking_id: UUID, current_user: dict = Depends(get_current_user)):
    return booking_service.get_booking(booking_id, current_user)


@router.patch("/{booking_id}/cancel", response_model=BookingResponse, summary="Cancelar reserva")
def cancel_booking(
    booking_id: UUID,
    payload: BookingCancel,
    current_user: dict = Depends(require_role("cliente", "admin")),
):
    return booking_service.cancel_booking(booking_id, payload, current_user)


@router.patch("/{booking_id}/reschedule", response_model=BookingResponse, summary="Reprogramar reserva")
def reschedule_booking(
    booking_id: UUID,
    payload: BookingReschedule,
    current_user: dict = Depends(require_role("cliente", "admin")),
):
    return booking_service.reschedule_booking(booking_id, payload, current_user)


@router.patch("/{booking_id}/confirm", response_model=BookingResponse, summary="Confirmar reserva")
def confirm_booking(booking_id: UUID, current_user: dict = Depends(require_role("barbero", "admin"))):
    return booking_service.confirm_booking(booking_id, current_user)


@router.patch("/{booking_id}/complete", response_model=BookingResponse, summary="Marcar reserva completada")
def complete_booking(booking_id: UUID, current_user: dict = Depends(require_role("barbero", "admin"))):
    return booking_service.complete_booking(booking_id, current_user)


@router.patch("/{booking_id}/no-show", response_model=BookingResponse, summary="Marcar reserva como no-show")
def no_show_booking(booking_id: UUID, current_user: dict = Depends(require_role("barbero", "admin"))):
    return booking_service.mark_no_show(booking_id, current_user)


@router.get("/{booking_id}/history", response_model=List[BookingHistoryResponse], summary="Historial de reserva")
def get_booking_history(booking_id: UUID, current_user: dict = Depends(require_role("admin"))):
    return booking_service.get_booking_history(booking_id)
