from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from fastapi import Request

from app.dependencies import get_current_user
from app.routers.users import router as users_router
from app.database.queries import profiles as profile_queries
from app.database.queries import barbers as barber_queries
from app.utils.errors import AppException


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(users_router, prefix="/api/v1/users")

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "code": exc.code,
            },
        )

    return app


def test_users_list_requires_admin():
    app = _build_app()
    client = TestClient(app)

    response = client.get("/api/v1/users")
    assert response.status_code == 403


def test_users_available_for_barber_filters_linked_users(monkeypatch):
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    now = datetime.now(timezone.utc).isoformat()
    free_user_id = str(uuid4())
    linked_user_id = str(uuid4())
    linked_barber_id = str(uuid4())

    monkeypatch.setattr(
        profile_queries,
        "list_profiles",
        lambda **_: [
            {
                "id": free_user_id,
                "email": "free@demo.com",
                "full_name": "Libre",
                "phone": None,
                "avatar_url": None,
                "role": "barbero",
                "active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": linked_user_id,
                "email": "used@demo.com",
                "full_name": "Vinculado",
                "phone": None,
                "avatar_url": None,
                "role": "barbero",
                "active": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    monkeypatch.setattr(
        barber_queries,
        "list_barbers",
        lambda **_: [
            {
                "id": linked_barber_id,
                "user_id": linked_user_id,
                "full_name": "Barbero Vinculado",
                "active": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    client = TestClient(app)
    response = client.get("/api/v1/users?available_for_barber=true")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == free_user_id
    assert data[0]["linked_barber_id"] is None


def test_admin_can_promote_user_to_barbero(monkeypatch):
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    user_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(
        barber_queries,
        "get_barber_by_user_id",
        lambda *_ , **__: None,
    )
    monkeypatch.setattr(
        profile_queries,
        "update_profile_role",
        lambda *_: {
            "id": user_id,
            "email": "user@demo.com",
            "full_name": "Usuario",
            "phone": None,
            "avatar_url": None,
            "role": "barbero",
            "active": True,
            "created_at": now,
            "updated_at": now,
        },
    )

    client = TestClient(app)
    response = client.patch(f"/api/v1/users/{user_id}/role", json={"role": "barbero"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["role"] == "barbero"


def test_cannot_demote_to_cliente_if_linked_active_barber(monkeypatch):
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4()), "role": "admin", "active": True}

    user_id = str(uuid4())
    monkeypatch.setattr(
        barber_queries,
        "get_barber_by_user_id",
        lambda *_ , **__: {"id": str(uuid4()), "user_id": user_id, "active": True},
    )

    client = TestClient(app)
    response = client.patch(f"/api/v1/users/{user_id}/role", json={"role": "cliente"})
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
