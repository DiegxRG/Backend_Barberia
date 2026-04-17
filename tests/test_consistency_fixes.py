from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_optional_user
from app.routers.services import router as services_router
from app.routers.barbers import router as barbers_router
from app.routers.availability import router as availability_router
from app.services.service_service import service_service
from app.services.barber_service import barber_service
from app.services.availability_service import availability_service


def test_services_include_inactive_is_ignored_for_public(monkeypatch):
    app = FastAPI()
    app.include_router(services_router, prefix="/api/v1/services")

    calls = []

    def fake_list_services(include_inactive: bool = False):
        calls.append(include_inactive)
        return []

    monkeypatch.setattr(service_service, "list_services", fake_list_services)
    app.dependency_overrides[get_optional_user] = lambda: None

    client = TestClient(app)
    response = client.get("/api/v1/services?include_inactive=true")

    assert response.status_code == 200
    assert calls == [False]


def test_services_include_inactive_works_for_admin(monkeypatch):
    app = FastAPI()
    app.include_router(services_router, prefix="/api/v1/services")

    calls = []

    def fake_list_services(include_inactive: bool = False):
        calls.append(include_inactive)
        return []

    monkeypatch.setattr(service_service, "list_services", fake_list_services)
    app.dependency_overrides[get_optional_user] = lambda: {"role": "admin"}

    client = TestClient(app)
    response = client.get("/api/v1/services?include_inactive=true")

    assert response.status_code == 200
    assert calls == [True]


def test_barbers_include_inactive_is_ignored_for_public(monkeypatch):
    app = FastAPI()
    app.include_router(barbers_router, prefix="/api/v1/barbers")

    calls = []

    def fake_list_barbers(include_inactive: bool = False):
        calls.append(include_inactive)
        return []

    monkeypatch.setattr(barber_service, "list_barbers", fake_list_barbers)
    app.dependency_overrides[get_optional_user] = lambda: None

    client = TestClient(app)
    response = client.get("/api/v1/barbers?include_inactive=true")

    assert response.status_code == 200
    assert calls == [False]


def test_update_barber_accepts_barbero_role(monkeypatch):
    app = FastAPI()
    app.include_router(barbers_router, prefix="/api/v1/barbers")

    barber_id = uuid4()

    def fake_update_barber(_, __):
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": str(barber_id),
            "user_id": None,
            "full_name": "Barbero Test",
            "email": None,
            "phone": None,
            "specialty": None,
            "bio": None,
            "avatar_url": None,
            "active": True,
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(barber_service, "update_barber", fake_update_barber)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": str(uuid4()),
        "role": "barbero",
        "active": True,
    }

    client = TestClient(app)
    response = client.patch(f"/api/v1/barbers/{barber_id}", json={})

    assert response.status_code == 200


def test_availability_get_requires_auth():
    app = FastAPI()
    app.include_router(availability_router, prefix="/api/v1")

    client = TestClient(app)
    response = client.get(f"/api/v1/barbers/{uuid4()}/availability")

    assert response.status_code == 403


def test_availability_get_with_auth_returns_data(monkeypatch):
    app = FastAPI()
    app.include_router(availability_router, prefix="/api/v1")

    barber_id = uuid4()

    monkeypatch.setattr(
        availability_service,
        "get_full_availability",
        lambda _: {"barber_id": str(barber_id), "rules": [], "breaks": []},
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": str(uuid4()),
        "role": "cliente",
        "active": True,
    }

    client = TestClient(app)
    response = client.get(f"/api/v1/barbers/{barber_id}/availability")

    assert response.status_code == 200
    assert response.json()["barber_id"] == str(barber_id)


def test_days_off_get_requires_auth():
    app = FastAPI()
    app.include_router(availability_router, prefix="/api/v1")

    client = TestClient(app)
    response = client.get(f"/api/v1/barbers/{uuid4()}/days-off")

    assert response.status_code == 403


def test_days_off_get_with_auth_returns_data(monkeypatch):
    app = FastAPI()
    app.include_router(availability_router, prefix="/api/v1")

    monkeypatch.setattr(availability_service, "get_days_off", lambda *_: [])
    app.dependency_overrides[get_current_user] = lambda: {
        "id": str(uuid4()),
        "role": "cliente",
        "active": True,
    }

    client = TestClient(app)
    response = client.get(f"/api/v1/barbers/{uuid4()}/days-off")

    assert response.status_code == 200
    assert response.json() == []
