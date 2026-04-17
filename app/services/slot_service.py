from datetime import date, datetime, time, timedelta
from uuid import UUID

from app.config import settings
from app.database.queries import slots as queries
from app.models.slot import SlotsResponse, SlotItem
from app.utils.errors import NotFoundError
from app.utils.timezone import make_local_datetime, to_business_tz, get_day_bounds_utc


def _parse_time(value: str | time) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(value)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


class SlotService:
    def get_available_slots(self, barber_id: UUID, service_id: UUID, target_date: date) -> SlotsResponse:
        service = queries.get_service_by_id(service_id)
        if not service or not service.get("active", True):
            raise NotFoundError(detail=f"Servicio con ID {service_id} no encontrado o inactivo")

        barber = queries.get_barber_by_id(barber_id)
        if not barber or not barber.get("active", True):
            raise NotFoundError(detail=f"Barbero con ID {barber_id} no encontrado o inactivo")

        iso_dow = target_date.isoweekday()
        rule = queries.get_availability_rule(barber_id, iso_dow)
        if not rule:
            return self._build_response(barber_id, service_id, target_date, [])

        if queries.is_day_off(barber_id, target_date):
            return self._build_response(barber_id, service_id, target_date, [])

        duration = timedelta(minutes=int(service["duration_minutes"]))
        interval = timedelta(minutes=int(rule.get("slot_interval_minutes") or 30))

        rule_start = _parse_time(rule["start_time"])
        rule_end = _parse_time(rule["end_time"])
        end_limit = make_local_datetime(target_date, rule_end)

        breaks = queries.get_breaks_for_day(barber_id, iso_dow)
        break_ranges = [
            (
                make_local_datetime(target_date, _parse_time(item["start_time"])),
                make_local_datetime(target_date, _parse_time(item["end_time"])),
            )
            for item in breaks
        ]

        slots: list[dict] = []
        current = make_local_datetime(target_date, rule_start)
        while current + duration <= end_limit:
            slot_end = current + duration

            in_break = any(_overlaps(current, slot_end, brk_start, brk_end) for brk_start, brk_end in break_ranges)
            if not in_break:
                slots.append({"start": current, "end": slot_end, "available": True})

            current += interval

        if not slots:
            return self._build_response(barber_id, service_id, target_date, [])

        day_start_utc, day_end_utc = get_day_bounds_utc(target_date)
        bookings = queries.get_active_bookings(barber_id, day_start_utc, day_end_utc)

        for slot in slots:
            for booking in bookings:
                bk_start_local = to_business_tz(_parse_datetime(booking["start_at"]))
                bk_end_local = to_business_tz(_parse_datetime(booking["end_at"]))

                if _overlaps(slot["start"], slot["end"], bk_start_local, bk_end_local):
                    slot["available"] = False
                    break

        return self._build_response(barber_id, service_id, target_date, slots)

    def _build_response(self, barber_id: UUID, service_id: UUID, target_date: date, slots: list[dict]) -> SlotsResponse:
        return SlotsResponse(
            barber_id=barber_id,
            service_id=service_id,
            date=target_date,
            timezone=settings.BUSINESS_TIMEZONE,
            slots=[
                SlotItem(
                    start=slot["start"].strftime("%H:%M"),
                    end=slot["end"].strftime("%H:%M"),
                    available=slot["available"],
                )
                for slot in slots
            ],
        )


slot_service = SlotService()
