from uuid import UUID
from typing import List
from app.database.queries import services as queries
from app.models.service import ServiceCreate, ServiceUpdate, ServiceResponse
from app.utils.errors import NotFoundError, ValidationError as BadRequestError

VALID_CATEGORIES = {'corte', 'barba', 'combo', 'tratamiento', 'especial', 'general'}

class ServiceService:
    def list_services(self, include_inactive: bool = False) -> List[ServiceResponse]:
        data = queries.list_services(include_inactive)
        return [ServiceResponse(**item) for item in data]

    def get_service(self, service_id: UUID) -> ServiceResponse:
        data = queries.get_service_by_id(service_id)
        if not data:
            raise NotFoundError(f"Servicio con ID {service_id} no encontrado")
        return ServiceResponse(**data)

    def create_service(self, service_data: ServiceCreate) -> ServiceResponse:
        if service_data.category not in VALID_CATEGORIES:
            raise BadRequestError(f"Categoría inválida. Debe ser una de: {VALID_CATEGORIES}")
        
        # Convertir Decimal a float para pydantic/supabase si es necesario (el model_dump lo pasa como Decimal)
        data_dict = service_data.model_dump()
        data_dict["price"] = float(data_dict["price"])
        
        inserted = queries.create_service(data_dict)
        return ServiceResponse(**inserted)

    def update_service(self, service_id: UUID, service_data: ServiceUpdate) -> ServiceResponse:
        existing = queries.get_service_by_id(service_id)
        if not existing:
            raise NotFoundError(f"Servicio con ID {service_id} no encontrado")
            
        if service_data.category and service_data.category not in VALID_CATEGORIES:
            raise BadRequestError(f"Categoría inválida. Debe ser una de: {VALID_CATEGORIES}")

        update_data = service_data.model_dump(exclude_unset=True)
        if not update_data:
            return ServiceResponse(**existing)
            
        if "price" in update_data:
            update_data["price"] = float(update_data["price"])

        updated = queries.update_service(service_id, update_data)
        return ServiceResponse(**updated)

    def deactivate_service(self, service_id: UUID) -> ServiceResponse:
        existing = queries.get_service_by_id(service_id)
        if not existing:
            raise NotFoundError(f"Servicio con ID {service_id} no encontrado")
        
        updated = queries.update_service_status(service_id, active=False)
        return ServiceResponse(**updated)

service_service = ServiceService()
