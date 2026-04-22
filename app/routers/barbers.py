from fastapi import APIRouter, Depends, status, Body
from typing import List
from uuid import UUID

from app.models.barber import BarberCreate, BarberCreateWithAccount, BarberUpdate, BarberResponse, BarberWithServicesResponse
from app.models.service import ServiceResponse
from app.services.barber_service import barber_service
from app.dependencies import require_role, get_optional_user

router = APIRouter()

@router.get("", response_model=List[BarberResponse], summary="Obtener lista de barberos")
def get_barbers(include_inactive: bool = False, current_user: dict | None = Depends(get_optional_user)):
    """
    Retorna todos los barberos.
    - Por defecto solo los activos (que los clientes pueden ver).
    """
    allow_inactive = include_inactive and current_user is not None and current_user.get("role") == "admin"
    return barber_service.list_barbers(allow_inactive)

@router.get("/{barber_id}", response_model=BarberWithServicesResponse, summary="Obtener detalle de barbero")
def get_barber(barber_id: UUID):
    """Retorna detalles del barbero INCLUYENDO los servicios que ofrece."""
    return barber_service.get_barber(barber_id)

@router.post("", response_model=BarberResponse, status_code=status.HTTP_201_CREATED, summary="Crear barbero", dependencies=[Depends(require_role("admin"))])
def create_barber(barber: BarberCreate):
    """
    Registra un nuevo barbero en el sistema.
    Asignación opcional a un user_id de Auth.
    """
    return barber_service.create_barber(barber)


@router.post(
    "/with-account",
    response_model=BarberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear barbero con cuenta de acceso",
    dependencies=[Depends(require_role("admin"))],
)
def create_barber_with_account(payload: BarberCreateWithAccount):
    """
    Crea cuenta de acceso y registro de barbero vinculado en una sola operación.
    """
    return barber_service.create_barber_with_account(payload)

@router.patch("/{barber_id}", response_model=BarberResponse, summary="Actualizar barbero", dependencies=[Depends(require_role("admin", "barbero"))])
def update_barber(barber_id: UUID, barber: BarberUpdate):
    """Actualiza datos del barbero."""
    return barber_service.update_barber(barber_id, barber)

@router.delete("/{barber_id}", response_model=BarberResponse, summary="Desactivar barbero", dependencies=[Depends(require_role("admin"))])
def deactivate_barber(barber_id: UUID):
    """Inactiva un barbero (para no romper reservas previas)."""
    return barber_service.deactivate_barber(barber_id)

@router.put("/{barber_id}/services", response_model=List[ServiceResponse], summary="Asignar servicios al barbero", dependencies=[Depends(require_role("admin"))])
def update_barber_services(barber_id: UUID, service_ids: List[UUID] = Body(..., embed=True)):
    """
    Reemplaza todos los servicios asignados al barbero por esta nueva lista.
    """
    return barber_service.update_barber_services(barber_id, service_ids)
