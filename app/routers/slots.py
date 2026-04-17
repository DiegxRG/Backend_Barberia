from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.models.slot import SlotsResponse
from app.services.slot_service import slot_service

router = APIRouter()


@router.get("", response_model=SlotsResponse, summary="Obtener slots disponibles")
def get_slots(
    barber_id: UUID,
    service_id: UUID,
    target_date: date_type = Query(..., alias="date"),
    user=Depends(get_current_user),
):
    """
    Calcula slots disponibles de un barbero para un servicio y fecha específica.
    """
    return slot_service.get_available_slots(barber_id, service_id, target_date)
