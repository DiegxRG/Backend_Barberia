from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest

from app.config import settings
from app.database.queries import calendar_tokens as token_queries
from app.services.calendar_service import calendar_service
from app.utils.errors import BusinessRuleError, UnauthorizedError


def test_get_connect_url_requires_feature_flag(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ENABLED", False)

    with pytest.raises(BusinessRuleError):
        calendar_service.get_connect_url({"id": str(uuid4()), "role": "admin"})


def test_get_connect_url_generates_google_auth_url(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ENABLED", True)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/calendar/callback")
    monkeypatch.setattr(settings, "GOOGLE_SCOPES", "https://www.googleapis.com/auth/calendar.events")

    url = calendar_service.get_connect_url({"id": "user-1", "role": "admin"})

    assert "accounts.google.com" in url
    assert "client_id=cid" in url
    assert "redirect_uri=" in url
    assert "state=" in url


def test_callback_stores_encrypted_tokens(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ENABLED", True)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/calendar/callback")
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "jKQf7D9lx6xK0I4NrpD2bjP4cM1Jx-9JXx6p2XqVY2Q=")

    captured = {}

    monkeypatch.setattr(
        calendar_service,
        "_exchange_code_for_tokens",
        lambda *_: {"access_token": "a-token", "refresh_token": "r-token", "expires_in": 3600},
    )
    monkeypatch.setattr(token_queries, "get_token_by_user", lambda *_: None)

    def fake_upsert(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(token_queries, "upsert_token", fake_upsert)

    state = jwt.encode(
        {"sub": "user-1", "role": "admin", "exp": datetime.now(timezone.utc).timestamp() + 600},
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    result = calendar_service.handle_callback("code-123", state)

    assert result.connected is True
    assert captured["user_id"] == "user-1"
    assert captured["access_token"] != "a-token"
    assert captured["refresh_token"] != "r-token"


def test_callback_rejects_invalid_state(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ENABLED", True)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/calendar/callback")

    with pytest.raises(UnauthorizedError):
        calendar_service.handle_callback("code", "invalid-state")
