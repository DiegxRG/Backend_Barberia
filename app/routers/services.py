from fastapi import APIRouter, Depends, status
from typing import List
from uuid import UUID

from app.models.service import ServiceCreate, ServiceUpdate, ServiceResponse
from app.models.barber import BarberResponse
from app.services.service_service import service_service
from app.services.barber_service import barber_service
from app.dependencies import require_role, get_optional_user

router = APIRouter()

@router.get("", response_model=List[ServiceResponse], summary="Obtener lista de servicios")
def get_services(include_inactive: bool = False, current_user: dict | None = Depends(get_optional_user)):
    """
    Retorna todos los servicios.
    - Por defecto solo los activos.
    - Los inactivos solo se deben incluir para vistas de Admin.
    """
    allow_inactive = include_inactive and current_user is not None and current_user.get("role") == "admin"
    return service_service.list_services(allow_inactive)

@router.get("/{service_id}", response_model=ServiceResponse, summary="Obtener detalle de servicio")
def get_service(service_id: UUID):
    """Retorna los detalles de un servicio específico por su UUID."""
    return service_service.get_service(service_id)

@router.get("/{service_id}/barbers", response_model=List[BarberResponse], summary="Obtener barberos que ofrecen un servicio")
def get_barbers_for_service(service_id: UUID):
    """
    Retorna todos los barberos activos que ofrecen el servicio indicado.
    Usado por el flujo de reservas para filtrar barberos por servicio.
    """
    service_service.get_service(service_id)
    return barber_service.get_barbers_by_service(service_id)

@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED, summary="Crear un servicio", dependencies=[Depends(require_role("admin"))])
def create_service(service: ServiceCreate):
    """
    Crea un nuevo servicio en el catálogo.
    REQUERIDO: Rol de Administrador.
    """
    return service_service.create_service(service)

@router.patch("/{service_id}", response_model=ServiceResponse, summary="Actualizar servicio", dependencies=[Depends(require_role("admin"))])
def update_service(service_id: UUID, service: ServiceUpdate):
    """
    Actualiza parcialmente los datos de un servicio.
    REQUERIDO: Rol de Administrador.
    """
    return service_service.update_service(service_id, service)

@router.delete("/{service_id}", response_model=ServiceResponse, summary="Desactivar servicio (Soft Delete)", dependencies=[Depends(require_role("admin"))])
def deactivate_service(service_id: UUID):
    """
    Realiza un borrado lógico (active = false) del servicio.
    Para que las reservas históricas y reportes no se rompan.
    REQUERIDO: Rol de Administrador.
    """
    return service_service.deactivate_service(service_id)
