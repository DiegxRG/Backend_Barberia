from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from app.config import settings
from app.database.queries import bookings as queries
from app.models.booking import (
    BookingCreate,
    BookingResponse,
    BookingCancel,
    BookingReschedule,
    BookingHistoryResponse,
)
from app.services.slot_service import slot_service
from app.services.calendar_service import calendar_service
from app.utils.errors import (
    NotFoundError,
    ForbiddenError,
    BookingConflictError,
    BusinessRuleError,
    ValidationError,
)
from app.utils.cache import TTLCache
from app.utils.timezone import to_business_tz, now_utc


FINAL_STATUSES = {"cancelled", "completed", "no_show"}


class BookingService:
    def __init__(self):
        self._barber_by_user_cache: TTLCache[str, dict] = TTLCache(
            max_items=settings.QUERY_CACHE_MAX_ITEMS,
            ttl_seconds=settings.QUERY_CACHE_TTL_SECONDS,
        )

    def create_booking(self, payload: BookingCreate, current_user: dict) -> BookingResponse:
        role = current_user.get("role")
        if role not in {"cliente", "admin"}:
            raise ForbiddenError("Solo clientes o admins pueden crear reservas")

        client_user_id = self._resolve_client_user_id(payload, current_user)

        if payload.idempotency_key:
            existing = queries.get_booking_by_idempotency(payload.idempotency_key)
            if existing:
                return BookingResponse(**existing)

        service = queries.get_service_by_id(payload.service_id)
        if not service or not service.get("active", True):
            raise NotFoundError(detail=f"Servicio con ID {payload.service_id} no encontrado o inactivo")

        barber = queries.get_barber_by_id(payload.barber_id)
        if not barber or not barber.get("active", True):
            raise NotFoundError(detail=f"Barbero con ID {payload.barber_id} no encontrado o inactivo")

        if not queries.barber_offers_service(payload.barber_id, payload.service_id):
            raise ValidationError("El barbero no ofrece el servicio seleccionado")

        self._validate_advance_window(payload.start_at)
        self._validate_slot_is_available(
            payload.barber_id,
            payload.service_id,
            payload.start_at,
            service,
            barber,
        )

        duration = timedelta(minutes=int(service["duration_minutes"]))
        end_at = payload.start_at + duration

        overlap = queries.get_overlapping_bookings(payload.barber_id, payload.start_at, end_at)
        if overlap:
            raise BookingConflictError("El horario seleccionado ya no está disponible")

        data = {
            "client_user_id": client_user_id,
            "barber_id": str(payload.barber_id),
            "service_id": str(payload.service_id),
            "start_at": payload.start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "status": "pending",
            "notes": payload.notes,
            "idempotency_key": payload.idempotency_key,
        }

        try:
            created = queries.create_booking(data)
        except Exception as e:
            error_text = str(e).lower()
            if "exclude" in error_text or "conflict" in error_text or "duplicate" in error_text:
                raise BookingConflictError("El horario seleccionado ya no está disponible")
            raise

        queries.create_booking_history(
            {
                "booking_id": created["id"],
                "previous_status": None,
                "new_status": "pending",
                "changed_by": current_user.get("id"),
                "reason": "Reserva creada",
            }
        )
        created = self._sync_calendar_upsert(
            created,
            service_name=service.get("name"),
            barber_name=barber.get("full_name"),
        )
        return BookingResponse(**created)

    def list_bookings(
        self,
        current_user: dict,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = settings.DEFAULT_PAGE_SIZE,
    ) -> List[BookingResponse]:
        role = current_user.get("role")

        client_user_id = None
        barber_id = None

        if role == "cliente":
            client_user_id = current_user["id"]
        elif role == "barbero":
            barber = self._get_barber_by_user_id(current_user["id"])
            if not barber:
                return []
            barber_id = barber["id"]
        elif role != "admin":
            raise ForbiddenError("Rol no autorizado para listar reservas")

        data = queries.list_bookings(
            client_user_id=client_user_id,
            barber_id=barber_id,
            status=status,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return [BookingResponse(**item) for item in data]

    def get_booking(self, booking_id: UUID, current_user: dict) -> BookingResponse:
        booking = queries.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail=f"Reserva con ID {booking_id} no encontrada")

        self._assert_can_view_booking(booking, current_user)
        return BookingResponse(**booking)

    def cancel_booking(self, booking_id: UUID, payload: BookingCancel, current_user: dict) -> BookingResponse:
        booking = queries.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail=f"Reserva con ID {booking_id} no encontrada")

        self._assert_can_cancel_booking(booking, current_user)
        if booking["status"] in FINAL_STATUSES:
            raise BusinessRuleError("La reserva ya está finalizada y no puede cancelarse")

        updated = queries.update_booking(
            booking_id,
            {
                "status": "cancelled",
                "cancel_reason": payload.reason,
            },
        )

        queries.create_booking_history(
            {
                "booking_id": str(booking_id),
                "previous_status": booking["status"],
                "new_status": "cancelled",
                "changed_by": current_user.get("id"),
                "reason": payload.reason or "Reserva cancelada",
            }
        )
        updated = self._sync_calendar_delete(updated)
        return BookingResponse(**updated)

    def reschedule_booking(self, booking_id: UUID, payload: BookingReschedule, current_user: dict) -> BookingResponse:
        booking = queries.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail=f"Reserva con ID {booking_id} no encontrada")

        self._assert_can_cancel_booking(booking, current_user)
        if booking["status"] in FINAL_STATUSES:
            raise BusinessRuleError("La reserva ya está finalizada y no puede reprogramarse")

        self._validate_advance_window(payload.start_at)
        barber_id = UUID(booking["barber_id"])
        service_id = UUID(booking["service_id"])

        service = queries.get_service_by_id(service_id)
        if not service or not service.get("active", True):
            raise NotFoundError("Servicio no encontrado o inactivo")

        self._validate_slot_is_available(
            barber_id,
            service_id,
            payload.start_at,
            service,
        )

        end_at = payload.start_at + timedelta(minutes=int(service["duration_minutes"]))
        overlap = queries.get_overlapping_bookings(barber_id, payload.start_at, end_at)
        overlap = [item for item in overlap if item["id"] != str(booking_id)]
        if overlap:
            raise BookingConflictError("El nuevo horario ya no está disponible")

        previous_status = booking["status"]
        new_status = "pending" if previous_status == "confirmed" else previous_status

        updated = queries.update_booking(
            booking_id,
            {
                "start_at": payload.start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "status": new_status,
            },
        )

        queries.create_booking_history(
            {
                "booking_id": str(booking_id),
                "previous_status": previous_status,
                "new_status": new_status,
                "changed_by": current_user.get("id"),
                "reason": payload.reason or "Reserva reprogramada",
                "metadata": {
                    "previous_start_at": booking["start_at"],
                    "new_start_at": payload.start_at.isoformat(),
                },
            }
        )
        updated = self._sync_calendar_upsert(updated)
        return BookingResponse(**updated)

    def confirm_booking(self, booking_id: UUID, current_user: dict) -> BookingResponse:
        return self._change_status(booking_id, current_user, from_statuses={"pending"}, new_status="confirmed")

    def complete_booking(self, booking_id: UUID, current_user: dict) -> BookingResponse:
        return self._change_status(booking_id, current_user, from_statuses={"confirmed"}, new_status="completed")

    def mark_no_show(self, booking_id: UUID, current_user: dict) -> BookingResponse:
        return self._change_status(booking_id, current_user, from_statuses={"confirmed"}, new_status="no_show")

    def get_booking_history(self, booking_id: UUID) -> List[BookingHistoryResponse]:
        booking = queries.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail=f"Reserva con ID {booking_id} no encontrada")
        history = queries.get_booking_history(booking_id)
        return [BookingHistoryResponse(**item) for item in history]

    def _change_status(self, booking_id: UUID, current_user: dict, *, from_statuses: set[str], new_status: str) -> BookingResponse:
        booking = queries.get_booking_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail=f"Reserva con ID {booking_id} no encontrada")

        self._assert_can_manage_booking(booking, current_user)
        if booking["status"] not in from_statuses:
            raise BusinessRuleError(f"Transición no permitida: {booking['status']} -> {new_status}")

        updated = queries.update_booking(booking_id, {"status": new_status})
        queries.create_booking_history(
            {
                "booking_id": str(booking_id),
                "previous_status": booking["status"],
                "new_status": new_status,
                "changed_by": current_user.get("id"),
                "reason": f"Cambio de estado a {new_status}",
            }
        )
        if new_status == "confirmed":
            updated = self._sync_calendar_upsert(updated)
        return BookingResponse(**updated)

    def _validate_advance_window(self, start_at: datetime) -> None:
        now = now_utc()
        min_allowed = now + timedelta(minutes=settings.MIN_BOOKING_ADVANCE_MINUTES)
        max_allowed = now + timedelta(days=settings.MAX_BOOKING_ADVANCE_DAYS)

        if start_at < min_allowed:
            raise BusinessRuleError(
                f"La reserva debe hacerse con al menos {settings.MIN_BOOKING_ADVANCE_MINUTES} minutos de anticipación"
            )
        if start_at > max_allowed:
            raise BusinessRuleError(
                f"La reserva no puede superar {settings.MAX_BOOKING_ADVANCE_DAYS} días de anticipación"
            )

    def _validate_slot_is_available(
        self,
        barber_id: UUID,
        service_id: UUID,
        start_at: datetime,
        service_data: Optional[dict] = None,
        barber_data: Optional[dict] = None,
    ) -> None:
        local_start = to_business_tz(start_at)
        slots = slot_service.get_available_slots(
            barber_id,
            service_id,
            local_start.date(),
            service_data,
            barber_data,
        )
        target_start = local_start.strftime("%H:%M")

        matching_slot = next((slot for slot in slots.slots if slot.start == target_start), None)
        if not matching_slot or not matching_slot.available:
            raise BookingConflictError("El horario seleccionado ya no está disponible")

    def _resolve_client_user_id(self, payload: BookingCreate, current_user: dict) -> str:
        if current_user.get("role") == "cliente":
            return current_user["id"]
        if payload.client_user_id:
            return str(payload.client_user_id)
        return current_user["id"]

    def _assert_can_view_booking(self, booking: dict, current_user: dict) -> None:
        role = current_user.get("role")
        if role == "admin":
            return
        if role == "cliente" and booking["client_user_id"] == current_user.get("id"):
            return
        if role == "barbero":
            barber = queries.get_barber_by_user_id(current_user["id"])
            if barber and booking["barber_id"] == barber["id"]:
                return
        raise ForbiddenError("No tienes permisos para ver esta reserva")

    def _assert_can_cancel_booking(self, booking: dict, current_user: dict) -> None:
        role = current_user.get("role")
        if role == "admin":
            return
        if role == "cliente" and booking["client_user_id"] == current_user.get("id"):
            return
        raise ForbiddenError("No tienes permisos para modificar esta reserva")

    def _assert_can_manage_booking(self, booking: dict, current_user: dict) -> None:
        role = current_user.get("role")
        if role == "admin":
            return
        if role == "barbero":
            barber = queries.get_barber_by_user_id(current_user["id"])
            if barber and booking["barber_id"] == barber["id"]:
                return
        raise ForbiddenError("No tienes permisos para cambiar el estado de esta reserva")

    def _get_barber_by_user_id(self, user_id: str) -> dict | None:
        cached = self._barber_by_user_cache.get(user_id)
        if cached:
            return dict(cached)

        barber = queries.get_barber_by_user_id(user_id)
        if barber:
            self._barber_by_user_cache.set(user_id, barber)
            return barber
        return None

    def _sync_calendar_upsert(
        self,
        booking: dict,
        service_name: str | None = None,
        barber_name: str | None = None,
    ) -> dict:
        if not settings.GOOGLE_CALENDAR_ENABLED:
            return booking

        try:
            barber = queries.get_barber_by_id(UUID(str(booking["barber_id"])))
            if not barber or not barber.get("user_id"):
                return booking

            service_title = service_name
            if not service_title:
                service = queries.get_service_by_id(UUID(str(booking["service_id"])))
                service_title = service.get("name") if service else None

            event_id = calendar_service.upsert_booking_event(
                user_id=str(barber["user_id"]),
                booking=booking,
                service_name=service_title,
                barber_name=barber_name or barber.get("full_name"),
            )
            if not event_id or booking.get("calendar_event_id") == event_id:
                return booking

            updated = queries.update_booking(UUID(str(booking["id"])), {"calendar_event_id": event_id})
            return updated
        except Exception as e:
            # La reserva no debe fallar por un error externo de calendar.
            print(f"[WARN] Calendar sync upsert omitido para booking {booking.get('id')}: {str(e)}")
            return booking

    def _sync_calendar_delete(self, booking: dict) -> dict:
        if not settings.GOOGLE_CALENDAR_ENABLED:
            return booking

        try:
            barber = queries.get_barber_by_id(UUID(str(booking["barber_id"])))
            if not barber or not barber.get("user_id"):
                return booking

            calendar_service.delete_booking_event(
                user_id=str(barber["user_id"]),
                event_id=booking.get("calendar_event_id"),
            )

            if not booking.get("calendar_event_id"):
                return booking

            updated = queries.update_booking(UUID(str(booking["id"])), {"calendar_event_id": None})
            return updated
        except Exception as e:
            print(f"[WARN] Calendar sync delete omitido para booking {booking.get('id')}: {str(e)}")
            return booking


booking_service = BookingService()
