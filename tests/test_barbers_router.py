from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.routers.barbers import router as barbers_router
from app.services.barber_service import barber_service


def test_create_barber_with_account_requires_auth():
    app = FastAPI()
    app.include_router(barbers_router, prefix="/api/v1/barbers")
    client = TestClient(app)

    response = client.post(
        "/api/v1/barbers/with-account",
        json={
            "full_name": "Barbero Nuevo",
            "email": "barbero@demo.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 403


def test_create_barber_with_account_as_admin(monkeypatch):
    app = FastAPI()
    app.include_router(barbers_router, prefix="/api/v1/barbers")
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    now = datetime.now(timezone.utc).isoformat()
    barber_id = str(uuid4())
    user_id = str(uuid4())

    monkeypatch.setattr(
        barber_service,
        "create_barber_with_account",
        lambda *_: {
            "id": barber_id,
            "user_id": user_id,
            "full_name": "Barbero Nuevo",
            "email": "barbero@demo.com",
            "phone": None,
            "specialty": None,
            "bio": None,
            "avatar_url": None,
            "active": True,
            "created_at": now,
            "updated_at": now,
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/barbers/with-account",
        json={
            "full_name": "Barbero Nuevo",
            "email": "barbero@demo.com",
            "password": "secret123",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["id"] == barber_id
    assert response.json()["user_id"] == user_id
