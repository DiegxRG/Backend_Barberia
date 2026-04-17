from datetime import date
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.routers.slots import router as slots_router


def test_slots_endpoint_requires_auth():
    app = FastAPI()
    app.include_router(slots_router, prefix="/api/v1/slots")
    client = TestClient(app)
    response = client.get(
        "/api/v1/slots/",
        params={"barber_id": str(uuid4()), "service_id": str(uuid4()), "date": "2026-04-20"},
    )

    assert response.status_code == 403


def test_slots_endpoint_success_with_auth(monkeypatch):
    from app.services.slot_service import slot_service

    app = FastAPI()
    app.include_router(slots_router, prefix="/api/v1/slots")

    barber_id = uuid4()
    service_id = uuid4()

    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "cliente", "active": True}

    monkeypatch.setattr(
        slot_service,
        "get_available_slots",
        lambda *_: {
            "barber_id": str(barber_id),
            "service_id": str(service_id),
            "date": date(2026, 4, 20).isoformat(),
            "timezone": "America/Lima",
            "slots": [{"start": "09:00", "end": "09:30", "available": True}],
        },
    )

    client = TestClient(app)
    response = client.get(
        "/api/v1/slots/",
        params={"barber_id": str(barber_id), "service_id": str(service_id), "date": "2026-04-20"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["slots"][0]["available"] is True
