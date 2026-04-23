from uuid import UUID
from typing import List
import time

from app.database.queries import barbers as queries
from app.database.queries import profiles as profile_queries
from app.database.client import get_supabase
from app.models.barber import BarberCreate, BarberCreateWithAccount, BarberUpdate, BarberResponse, BarberWithServicesResponse
from app.models.service import ServiceResponse
from app.services.slot_service import slot_service
from app.utils.errors import NotFoundError, ValidationError, InternalError

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
        self._validate_user_link(data_dict.get("user_id"))
        inserted = queries.create_barber(data_dict)
        slot_service.clear_cache()
        return BarberResponse(**inserted)

    def create_barber_with_account(self, payload: BarberCreateWithAccount) -> BarberResponse:
        """
        Crea cuenta de auth.users + promueve perfil a barbero + crea registro barbers vinculado.
        """
        supabase = get_supabase()
        created_user_id: str | None = None

        try:
            created_user = supabase.auth.admin.create_user(
                {
                    "email": payload.email,
                    "password": payload.password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": payload.full_name},
                }
            )
            created_user_id = created_user.user.id

            profile = None
            for _ in range(5):
                profile = profile_queries.get_profile(created_user_id)
                if profile:
                    break
                time.sleep(0.2)

            if not profile:
                raise InternalError("No se pudo resolver perfil recién creado en Supabase")

            profile_queries.update_profile_role(created_user_id, "barbero")
            profile_queries.update_profile(created_user_id, {"full_name": payload.full_name})

            barber_data = payload.model_dump(exclude={"password"}, exclude_none=True)
            barber_data["user_id"] = created_user_id
            barber_data["email"] = payload.email

            inserted = queries.create_barber(barber_data)
            slot_service.clear_cache()
            return BarberResponse(**inserted)
        except Exception as e:
            if created_user_id:
                try:
                    supabase.auth.admin.delete_user(created_user_id)
                except Exception:
                    pass

            if isinstance(e, (ValidationError, InternalError)):
                raise
            raise ValidationError(f"No se pudo crear cuenta de barbero: {str(e)}")

    def update_barber(self, barber_id: UUID, barber_data: BarberUpdate) -> BarberResponse:
        existing = queries.get_barber_by_id(barber_id)
        if not existing:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")

        update_data = barber_data.model_dump(exclude_unset=True)
        if not update_data:
            return BarberResponse(**existing)

        self._validate_user_link(update_data.get("user_id"), current_barber_id=existing["id"])
        updated = queries.update_barber(barber_id, update_data)
        slot_service.clear_cache()
        return BarberResponse(**updated)

    def deactivate_barber(self, barber_id: UUID) -> BarberResponse:
        existing = queries.get_barber_by_id(barber_id)
        if not existing:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")
        
        updated = queries.update_barber_status(barber_id, active=False)
        slot_service.clear_cache()
        return BarberResponse(**updated)

    def update_barber_services(self, barber_id: UUID, service_ids: List[UUID]) -> List[ServiceResponse]:
        existing = queries.get_barber_by_id(barber_id)
        if not existing:
            raise NotFoundError(f"Barbero con ID {barber_id} no encontrado")
            
        queries.assign_services_to_barber(barber_id, service_ids)
        new_services = queries.get_barber_services(barber_id)
        slot_service.clear_cache()
        return [ServiceResponse(**s) for s in new_services]

    def get_barbers_by_service(self, service_id: UUID) -> List[BarberResponse]:
        data = queries.get_barbers_by_service(service_id)
        return [BarberResponse(**item) for item in data]

    def _validate_user_link(self, user_id: UUID | None, current_barber_id: str | None = None) -> None:
        if user_id is None:
            return

        user_id_str = str(user_id)
        profile = profile_queries.get_profile(user_id_str)
        if not profile:
            raise ValidationError("El user_id indicado no existe en profiles")
        if profile.get("role") != "barbero":
            raise ValidationError("El user_id indicado no tiene rol 'barbero'")
        if not profile.get("active", True):
            raise ValidationError("No se puede vincular un usuario inactivo")

        linked_barber = queries.get_barber_by_user_id(user_id_str, include_inactive=True)
        if linked_barber and str(linked_barber["id"]) != str(current_barber_id):
            raise ValidationError("El user_id indicado ya está vinculado a otro barbero")

barber_service = BarberService()
