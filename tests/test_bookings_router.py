from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.routers.bookings import router as bookings_router


def test_bookings_list_requires_auth():
    app = FastAPI()
    app.include_router(bookings_router, prefix="/api/v1/bookings")

    client = TestClient(app)
    response = client.get("/api/v1/bookings")

    assert response.status_code == 403


def test_bookings_create_works_for_cliente(monkeypatch):
    from app.services.booking_service import booking_service

    app = FastAPI()
    app.include_router(bookings_router, prefix="/api/v1/bookings")
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "cliente", "active": True}

    booking_id = uuid4()
    start_at = datetime.now(timezone.utc) + timedelta(days=1)

    monkeypatch.setattr(
        booking_service,
        "create_booking",
        lambda *_: {
            "id": str(booking_id),
            "client_user_id": str(uuid4()),
            "barber_id": str(uuid4()),
            "service_id": str(uuid4()),
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(minutes=30)).isoformat(),
            "status": "pending",
            "notes": None,
            "cancel_reason": None,
            "idempotency_key": "idem-123",
            "calendar_event_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/bookings",
        json={
            "barber_id": str(uuid4()),
            "service_id": str(uuid4()),
            "start_at": start_at.isoformat(),
            "idempotency_key": "idem-123",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
