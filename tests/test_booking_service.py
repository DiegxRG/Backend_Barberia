from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.database.queries import bookings as booking_queries
from app.config import settings
from app.models.booking import BookingCreate, BookingCancel, BookingReschedule
from app.services.calendar_service import calendar_service
from app.services.booking_service import booking_service
from app.utils.errors import ForbiddenError, BookingConflictError


def _base_payload(start_at: datetime | None = None) -> BookingCreate:
    return BookingCreate(
        barber_id=uuid4(),
        service_id=uuid4(),
        start_at=start_at or (datetime.now(timezone.utc) + timedelta(hours=2)),
        notes="Corte de prueba",
        idempotency_key="idem-001",
    )


def test_create_booking_returns_existing_for_same_idempotency(monkeypatch):
    payload = _base_payload()
    existing_id = str(uuid4())

    monkeypatch.setattr(booking_queries, "get_booking_by_idempotency", lambda _: {
        "id": existing_id,
        "client_user_id": str(uuid4()),
        "barber_id": str(payload.barber_id),
        "service_id": str(payload.service_id),
        "start_at": payload.start_at.isoformat(),
        "end_at": (payload.start_at + timedelta(minutes=30)).isoformat(),
        "status": "pending",
        "notes": payload.notes,
        "cancel_reason": None,
        "idempotency_key": "idem-001",
        "calendar_event_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    result = booking_service.create_booking(payload, {"id": str(uuid4()), "role": "cliente"})

    assert str(result.id) == existing_id


def test_create_booking_success(monkeypatch):
    payload = _base_payload()
    now = datetime.now(timezone.utc).isoformat()
    booking_id = str(uuid4())

    monkeypatch.setattr(booking_queries, "get_booking_by_idempotency", lambda _: None)
    monkeypatch.setattr(booking_queries, "get_service_by_id", lambda _: {"id": str(payload.service_id), "duration_minutes": 30, "active": True})
    monkeypatch.setattr(booking_queries, "get_barber_by_id", lambda _: {"id": str(payload.barber_id), "active": True})
    monkeypatch.setattr(booking_queries, "barber_offers_service", lambda *_: True)
    monkeypatch.setattr(booking_service, "_validate_advance_window", lambda *_: None)
    monkeypatch.setattr(booking_service, "_validate_slot_is_available", lambda *_: None)
    monkeypatch.setattr(booking_queries, "get_overlapping_bookings", lambda *_: [])
    monkeypatch.setattr(booking_queries, "create_booking_history", lambda *_: {"ok": True})
    monkeypatch.setattr(
        booking_queries,
        "create_booking",
        lambda data: {
            "id": booking_id,
            "client_user_id": data["client_user_id"],
            "barber_id": data["barber_id"],
            "service_id": data["service_id"],
            "start_at": data["start_at"],
            "end_at": data["end_at"],
            "status": "pending",
            "notes": data["notes"],
            "cancel_reason": None,
            "idempotency_key": data["idempotency_key"],
            "calendar_event_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )

    result = booking_service.create_booking(payload, {"id": str(uuid4()), "role": "cliente"})

    assert str(result.id) == booking_id
    assert result.status == "pending"


def test_create_booking_raises_conflict_when_overlap(monkeypatch):
    payload = _base_payload()

    monkeypatch.setattr(booking_queries, "get_booking_by_idempotency", lambda *_: None)
    monkeypatch.setattr(booking_queries, "get_service_by_id", lambda *_: {"duration_minutes": 30, "active": True})
    monkeypatch.setattr(booking_queries, "get_barber_by_id", lambda *_: {"active": True})
    monkeypatch.setattr(booking_queries, "barber_offers_service", lambda *_: True)
    monkeypatch.setattr(booking_service, "_validate_advance_window", lambda *_: None)
    monkeypatch.setattr(booking_service, "_validate_slot_is_available", lambda *_: None)
    monkeypatch.setattr(booking_queries, "get_overlapping_bookings", lambda *_: [{"id": str(uuid4())}])

    with pytest.raises(BookingConflictError):
        booking_service.create_booking(payload, {"id": str(uuid4()), "role": "cliente"})


def test_reschedule_confirmed_returns_pending(monkeypatch):
    booking_id = uuid4()
    client_user_id = str(uuid4())
    start_at = datetime.now(timezone.utc) + timedelta(days=1)
    new_start = start_at + timedelta(hours=2)
    payload = BookingReschedule(start_at=new_start)
    now = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(
        booking_queries,
        "get_booking_by_id",
        lambda *_: {
                "id": str(booking_id),
                "client_user_id": client_user_id,
            "barber_id": str(uuid4()),
            "service_id": str(uuid4()),
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(minutes=30)).isoformat(),
            "status": "confirmed",
            "notes": None,
            "cancel_reason": None,
            "idempotency_key": None,
            "calendar_event_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    monkeypatch.setattr(booking_service, "_assert_can_cancel_booking", lambda *_: None)
    monkeypatch.setattr(booking_service, "_validate_advance_window", lambda *_: None)
    monkeypatch.setattr(booking_service, "_validate_slot_is_available", lambda *_: None)
    monkeypatch.setattr(booking_queries, "get_service_by_id", lambda *_: {"duration_minutes": 30, "active": True})
    monkeypatch.setattr(booking_queries, "get_overlapping_bookings", lambda *_: [])
    monkeypatch.setattr(booking_queries, "create_booking_history", lambda *_: {"ok": True})
    monkeypatch.setattr(
        booking_queries,
        "update_booking",
        lambda _, data: {
                "id": str(booking_id),
                "client_user_id": client_user_id,
            "barber_id": str(uuid4()),
            "service_id": str(uuid4()),
            "start_at": data["start_at"],
            "end_at": data["end_at"],
            "status": data["status"],
            "notes": None,
            "cancel_reason": None,
            "idempotency_key": None,
            "calendar_event_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )

    result = booking_service.reschedule_booking(booking_id, payload, {"id": client_user_id, "role": "cliente"})

    assert result.status == "pending"


def test_barbero_cannot_cancel_client_booking(monkeypatch):
    booking_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(
        booking_queries,
        "get_booking_by_id",
        lambda *_: {
            "id": str(booking_id),
            "client_user_id": "client-1",
            "barber_id": str(uuid4()),
            "service_id": str(uuid4()),
            "start_at": datetime.now(timezone.utc).isoformat(),
            "end_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "notes": None,
            "cancel_reason": None,
            "idempotency_key": None,
            "calendar_event_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )

    with pytest.raises(ForbiddenError):
        booking_service.cancel_booking(booking_id, BookingCancel(reason="x"), {"id": "barber-user", "role": "barbero"})


def test_create_booking_syncs_google_calendar_when_enabled(monkeypatch):
    payload = _base_payload()
    now = datetime.now(timezone.utc).isoformat()
    booking_id = str(uuid4())
    barber_user_id = str(uuid4())

    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ENABLED", True)
    monkeypatch.setattr(booking_queries, "get_booking_by_idempotency", lambda *_: None)
    monkeypatch.setattr(
        booking_queries,
        "get_service_by_id",
        lambda *_: {"id": str(payload.service_id), "name": "Corte", "duration_minutes": 30, "active": True},
    )
    monkeypatch.setattr(
        booking_queries,
        "get_barber_by_id",
        lambda *_: {"id": str(payload.barber_id), "user_id": barber_user_id, "full_name": "Barbero 1", "active": True},
    )
    monkeypatch.setattr(booking_queries, "barber_offers_service", lambda *_: True)
    monkeypatch.setattr(booking_service, "_validate_advance_window", lambda *_: None)
    monkeypatch.setattr(booking_service, "_validate_slot_is_available", lambda *_: None)
    monkeypatch.setattr(booking_queries, "get_overlapping_bookings", lambda *_: [])
    monkeypatch.setattr(booking_queries, "create_booking_history", lambda *_: {"ok": True})
    monkeypatch.setattr(calendar_service, "upsert_booking_event", lambda **_: "evt-123")
    monkeypatch.setattr(
        booking_queries,
        "create_booking",
        lambda data: {
            "id": booking_id,
            "client_user_id": data["client_user_id"],
            "barber_id": data["barber_id"],
            "service_id": data["service_id"],
            "start_at": data["start_at"],
            "end_at": data["end_at"],
            "status": "pending",
            "notes": data["notes"],
            "cancel_reason": None,
            "idempotency_key": data["idempotency_key"],
            "calendar_event_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    monkeypatch.setattr(
        booking_queries,
        "update_booking",
        lambda _, data: {
            "id": booking_id,
            "client_user_id": str(uuid4()),
            "barber_id": str(payload.barber_id),
            "service_id": str(payload.service_id),
            "start_at": payload.start_at.isoformat(),
            "end_at": (payload.start_at + timedelta(minutes=30)).isoformat(),
            "status": "pending",
            "notes": payload.notes,
            "cancel_reason": None,
            "idempotency_key": payload.idempotency_key,
            "calendar_event_id": data.get("calendar_event_id"),
            "created_at": now,
            "updated_at": now,
        },
    )

    result = booking_service.create_booking(payload, {"id": str(uuid4()), "role": "cliente"})
    assert result.calendar_event_id == "evt-123"


def test_cancel_booking_removes_google_calendar_event_when_enabled(monkeypatch):
    booking_id = uuid4()
    barber_id = uuid4()
    client_user_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "id": str(booking_id),
        "client_user_id": client_user_id,
        "barber_id": str(barber_id),
        "service_id": str(uuid4()),
        "start_at": datetime.now(timezone.utc).isoformat(),
        "end_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "status": "pending",
        "notes": None,
        "cancel_reason": None,
        "idempotency_key": None,
        "calendar_event_id": "evt-1",
        "created_at": now,
        "updated_at": now,
    }
    delete_calls = []

    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ENABLED", True)
    monkeypatch.setattr(booking_queries, "get_booking_by_id", lambda *_: dict(state))
    monkeypatch.setattr(
        booking_queries,
        "get_barber_by_id",
        lambda *_: {"id": str(barber_id), "user_id": str(uuid4()), "full_name": "Barbero 1", "active": True},
    )
    monkeypatch.setattr(
        booking_queries,
        "update_booking",
        lambda _, data: (state.update(data) or dict(state)),
    )
    monkeypatch.setattr(booking_queries, "create_booking_history", lambda *_: {"ok": True})
    monkeypatch.setattr(
        calendar_service,
        "delete_booking_event",
        lambda **kwargs: delete_calls.append(kwargs),
    )

    result = booking_service.cancel_booking(booking_id, BookingCancel(reason="No ire"), {"id": client_user_id, "role": "cliente"})

    assert result.status == "cancelled"
    assert result.calendar_event_id is None
    assert len(delete_calls) == 1
    assert delete_calls[0]["event_id"] == "evt-1"
