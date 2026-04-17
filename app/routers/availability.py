from fastapi import APIRouter, Depends, status
from typing import List
from uuid import UUID
from datetime import date

from app.models.availability import (
    BulkAvailabilityRuleCreate, AvailabilityRuleResponse,
    BreakCreate, BreakResponse,
    DayOffCreate, DayOffResponse,
    FullAvailabilityResponse
)
from app.services.availability_service import availability_service
from app.dependencies import require_role, get_current_user

router = APIRouter()

# --- DISPONIBILIDAD Y BREAKS ---
@router.get("/barbers/{barber_id}/availability", response_model=FullAvailabilityResponse, summary="Obtener horario base de barbero")
def get_availability(barber_id: UUID, user = Depends(get_current_user)):
    """Devuelve las reglas de atención (1=Lunes..7=Dom) y los breaks del barbero."""
    return availability_service.get_full_availability(barber_id)

@router.put("/barbers/{barber_id}/availability", response_model=List[AvailabilityRuleResponse], summary="Establecer reglas base (Reemplaza)")
def set_availability(barber_id: UUID, data: BulkAvailabilityRuleCreate, user = Depends(require_role("admin", "barbero"))):
    """
    Reemplaza TODAS las reglas base del barbero por la nueva lista.
    Si se manda una lista vacía, borra la agenda.
    """
    return availability_service.set_availability_rules(barber_id, data.rules)

@router.post("/barbers/{barber_id}/breaks", response_model=BreakResponse, status_code=status.HTTP_201_CREATED, summary="Agregar un descanso")
def add_break(barber_id: UUID, break_data: BreakCreate, user = Depends(require_role("admin", "barbero"))):
    """Agrega un bloque de descanso recurrente en un día de la semana para el barbero."""
    return availability_service.create_break(barber_id, break_data)

@router.delete("/breaks/{break_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar descanso")
def remove_break(break_id: UUID, user = Depends(require_role("admin", "barbero"))):
    """Elimina una pausa por su ID transversal."""
    availability_service.delete_break(break_id)

# --- DAYS OFF ---
@router.get("/barbers/{barber_id}/days-off", response_model=List[DayOffResponse], summary="Obtener faltas/vacaciones")
def get_days_off(barber_id: UUID, from_date: date = None, user = Depends(get_current_user)):
    """Obtiene los días puntuales bloqueados."""
    return availability_service.get_days_off(barber_id, from_date)

@router.post("/barbers/{barber_id}/days-off", response_model=DayOffResponse, status_code=status.HTTP_201_CREATED, summary="Registrar día libre")
def add_day_off(barber_id: UUID, data: DayOffCreate, user = Depends(require_role("admin", "barbero"))):
    """Bloquea un día específico completo."""
    return availability_service.create_day_off(barber_id, data)

@router.delete("/barbers/{barber_id}/days-off/{target_date}", status_code=status.HTTP_204_NO_CONTENT, summary="Quitar día libre")
def remove_day_off(barber_id: UUID, target_date: date, user = Depends(require_role("admin", "barbero"))):
    """Desbloquea el día quitándolo de la lista de Day Offs."""
    availability_service.delete_day_off(barber_id, target_date)
