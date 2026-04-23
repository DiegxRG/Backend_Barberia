from datetime import date, datetime, time, timedelta
from uuid import UUID

from app.config import settings
from app.database.queries import slots as queries
from app.models.slot import SlotsResponse, SlotItem
from app.utils.cache import TTLCache
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
    def __init__(self):
        self._catalog_cache: TTLCache[tuple[str, str], dict] = TTLCache(
            max_items=settings.QUERY_CACHE_MAX_ITEMS,
            ttl_seconds=settings.QUERY_CACHE_TTL_SECONDS,
        )
        self._schedule_cache: TTLCache[tuple[str, str, int], dict | list[dict]] = TTLCache(
            max_items=settings.QUERY_CACHE_MAX_ITEMS,
            ttl_seconds=settings.QUERY_CACHE_TTL_SECONDS,
        )

    def get_available_slots(
        self,
        barber_id: UUID,
        service_id: UUID,
        target_date: date,
        service_data: dict | None = None,
        barber_data: dict | None = None,
    ) -> SlotsResponse:
        service = service_data or self._get_service_cached(service_id)
        if not service or not service.get("active", True):
            raise NotFoundError(detail=f"Servicio con ID {service_id} no encontrado o inactivo")

        barber = barber_data or self._get_barber_cached(barber_id)
        if not barber or not barber.get("active", True):
            raise NotFoundError(detail=f"Barbero con ID {barber_id} no encontrado o inactivo")

        iso_dow = target_date.isoweekday()
        rule = self._get_rule_cached(barber_id, iso_dow)
        if not rule:
            return self._build_response(barber_id, service_id, target_date, [])

        if queries.is_day_off(barber_id, target_date):
            return self._build_response(barber_id, service_id, target_date, [])

        duration = timedelta(minutes=int(service["duration_minutes"]))
        interval = timedelta(minutes=int(rule.get("slot_interval_minutes") or 30))

        rule_start = _parse_time(rule["start_time"])
        rule_end = _parse_time(rule["end_time"])
        end_limit = make_local_datetime(target_date, rule_end)

        breaks = self._get_breaks_cached(barber_id, iso_dow)
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

    def clear_cache(self) -> None:
        self._catalog_cache.clear()
        self._schedule_cache.clear()

    def _get_service_cached(self, service_id: UUID) -> dict | None:
        cache_key = ("service", str(service_id))
        cached = self._catalog_cache.get(cache_key)
        if cached:
            return dict(cached)

        service = queries.get_service_by_id(service_id)
        if service:
            self._catalog_cache.set(cache_key, service)
        return service

    def _get_barber_cached(self, barber_id: UUID) -> dict | None:
        cache_key = ("barber", str(barber_id))
        cached = self._catalog_cache.get(cache_key)
        if cached:
            return dict(cached)

        barber = queries.get_barber_by_id(barber_id)
        if barber:
            self._catalog_cache.set(cache_key, barber)
        return barber

    def _get_rule_cached(self, barber_id: UUID, iso_dow: int) -> dict | None:
        cache_key = ("rule", str(barber_id), iso_dow)
        cached = self._schedule_cache.get(cache_key)
        if isinstance(cached, dict):
            return dict(cached)

        rule = queries.get_availability_rule(barber_id, iso_dow)
        if rule:
            self._schedule_cache.set(cache_key, rule)
        return rule

    def _get_breaks_cached(self, barber_id: UUID, iso_dow: int) -> list[dict]:
        cache_key = ("breaks", str(barber_id), iso_dow)
        cached = self._schedule_cache.get(cache_key)
        if isinstance(cached, list):
            return [dict(item) for item in cached]

        breaks = queries.get_breaks_for_day(barber_id, iso_dow)
        self._schedule_cache.set(cache_key, breaks)
        return breaks

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
