from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.routers.calendar import router as calendar_router


def test_calendar_status_requires_auth():
    app = FastAPI()
    app.include_router(calendar_router, prefix="/api/v1/calendar")
    client = TestClient(app)

    response = client.get("/api/v1/calendar/status")
    assert response.status_code == 403


def test_calendar_connect_redirects(monkeypatch):
    from app.services.calendar_service import calendar_service

    app = FastAPI()
    app.include_router(calendar_router, prefix="/api/v1/calendar")
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    monkeypatch.setattr(calendar_service, "get_connect_url", lambda *_: "https://accounts.google.com/o/oauth2/v2/auth?x=1")

    client = TestClient(app)
    response = client.get("/api/v1/calendar/connect", follow_redirects=False)
    app.dependency_overrides.clear()

    assert response.status_code == 302
    assert "accounts.google.com" in response.headers["location"]


def test_calendar_connect_url_success(monkeypatch):
    from app.services.calendar_service import calendar_service

    app = FastAPI()
    app.include_router(calendar_router, prefix="/api/v1/calendar")
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    monkeypatch.setattr(calendar_service, "get_connect_url", lambda *_: "https://accounts.google.com/o/oauth2/v2/auth?x=2")

    client = TestClient(app)
    response = client.get("/api/v1/calendar/connect-url")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "accounts.google.com" in response.json()["auth_url"]


def test_calendar_status_success(monkeypatch):
    from app.services.calendar_service import calendar_service

    app = FastAPI()
    app.include_router(calendar_router, prefix="/api/v1/calendar")
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "barbero", "active": True}

    monkeypatch.setattr(
        calendar_service,
        "get_status",
        lambda *_: {
            "connected": True,
            "calendar_id": "primary",
            "token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )

    client = TestClient(app)
    response = client.get("/api/v1/calendar/status")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["connected"] is True


def test_calendar_settings_prefix_status_success(monkeypatch):
    from app.services.calendar_service import calendar_service

    app = FastAPI()
    app.include_router(calendar_router, prefix="/api/v1/settings/calendar")
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    monkeypatch.setattr(
        calendar_service,
        "get_status",
        lambda *_: {
            "connected": True,
            "calendar_id": "primary",
            "token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )

    client = TestClient(app)
    response = client.get("/api/v1/settings/calendar/status")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["connected"] is True
