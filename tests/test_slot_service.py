from datetime import date, datetime, timezone
from uuid import uuid4

from app.database.queries import slots as slot_queries
from app.services.slot_service import slot_service


def _patch_base(monkeypatch, duration_minutes=30, start_time="09:00:00", end_time="11:00:00", interval=30):
    monkeypatch.setattr(
        slot_queries,
        "get_service_by_id",
        lambda _: {"id": str(uuid4()), "duration_minutes": duration_minutes, "active": True},
    )
    monkeypatch.setattr(
        slot_queries,
        "get_barber_by_id",
        lambda _: {"id": str(uuid4()), "full_name": "Barbero Test", "active": True},
    )
    monkeypatch.setattr(
        slot_queries,
        "get_availability_rule",
        lambda *_: {
            "day_of_week": 1,
            "start_time": start_time,
            "end_time": end_time,
            "slot_interval_minutes": interval,
            "active": True,
        },
    )
    monkeypatch.setattr(slot_queries, "is_day_off", lambda *_: False)
    monkeypatch.setattr(slot_queries, "get_breaks_for_day", lambda *_: [])
    monkeypatch.setattr(slot_queries, "get_active_bookings", lambda *_: [])


def test_returns_empty_when_no_rule(monkeypatch):
    _patch_base(monkeypatch)
    monkeypatch.setattr(slot_queries, "get_availability_rule", lambda *_: None)

    result = slot_service.get_available_slots(uuid4(), uuid4(), date(2026, 4, 20))

    assert result.slots == []


def test_returns_empty_when_day_off(monkeypatch):
    _patch_base(monkeypatch)
    monkeypatch.setattr(slot_queries, "is_day_off", lambda *_: True)

    result = slot_service.get_available_slots(uuid4(), uuid4(), date(2026, 4, 20))

    assert result.slots == []


def test_filters_slots_that_overlap_breaks_by_full_duration(monkeypatch):
    _patch_base(monkeypatch, duration_minutes=60, start_time="09:00:00", end_time="12:00:00", interval=30)
    monkeypatch.setattr(
        slot_queries,
        "get_breaks_for_day",
        lambda *_: [{"start_time": "10:30:00", "end_time": "11:00:00", "active": True}],
    )

    result = slot_service.get_available_slots(uuid4(), uuid4(), date(2026, 4, 20))
    starts = [slot.start for slot in result.slots]

    assert starts == ["09:00", "09:30", "11:00"]


def test_marks_booked_slots_as_unavailable(monkeypatch):
    _patch_base(monkeypatch, duration_minutes=30, start_time="09:00:00", end_time="11:00:00", interval=30)

    monkeypatch.setattr(
        slot_queries,
        "get_active_bookings",
        lambda *_: [
            {
                "start_at": datetime(2026, 4, 20, 14, 30, tzinfo=timezone.utc).isoformat(),
                "end_at": datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc).isoformat(),
                "status": "confirmed",
            }
        ],
    )

    result = slot_service.get_available_slots(uuid4(), uuid4(), date(2026, 4, 20))
    availability = {slot.start: slot.available for slot in result.slots}

    assert availability["09:00"] is True
    assert availability["09:30"] is False
    assert availability["10:00"] is True
    assert availability["10:30"] is True


def test_service_longer_than_window_returns_empty(monkeypatch):
    _patch_base(monkeypatch, duration_minutes=90, start_time="09:00:00", end_time="10:00:00", interval=30)

    result = slot_service.get_available_slots(uuid4(), uuid4(), date(2026, 4, 20))

    assert result.slots == []
