from uuid import UUID
from typing import List
from app.database.queries import barbers as queries
from app.models.barber import BarberCreate, BarberUpdate, BarberResponse, BarberWithServicesResponse
from app.models.service import ServiceResponse
from app.utils.errors import NotFoundError

class BarberService:
    def list_barbers(self, include_inactive: bool = False) -> List[BarberResponse]:
        data = queries.list_barbers(include_inactive)
        return [BarberResponse(**item) for item in data]

    def get_barber(self, barber_id: UUID) -> BarberWithServicesResponse:
        barber_data = queries.get_barber_by_id(barber_id)
        if not barber_data:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")
            
        services_data = queries.get_barber_services(barber_id)
        
        response = BarberWithServicesResponse(**barber_data)
        response.services = [ServiceResponse(**s) for s in services_data]
        return response

    def create_barber(self, barber_data: BarberCreate) -> BarberResponse:
        data_dict = barber_data.model_dump(exclude_none=True)
        inserted = queries.create_barber(data_dict)
        return BarberResponse(**inserted)

    def update_barber(self, barber_id: UUID, barber_data: BarberUpdate) -> BarberResponse:
        existing = queries.get_barber_by_id(barber_id)
        if not existing:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")

        update_data = barber_data.model_dump(exclude_unset=True)
        if not update_data:
            return BarberResponse(**existing)

        updated = queries.update_barber(barber_id, update_data)
        return BarberResponse(**updated)

    def deactivate_barber(self, barber_id: UUID) -> BarberResponse:
        existing = queries.get_barber_by_id(barber_id)
        if not existing:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")
        
        updated = queries.update_barber_status(barber_id, active=False)
        return BarberResponse(**updated)

    def update_barber_services(self, barber_id: UUID, service_ids: List[UUID]) -> List[ServiceResponse]:
        existing = queries.get_barber_by_id(barber_id)
        if not existing:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")
            
        queries.assign_services_to_barber(barber_id, service_ids)
        new_services = queries.get_barber_services(barber_id)
        return [ServiceResponse(**s) for s in new_services]

barber_service = BarberService()
