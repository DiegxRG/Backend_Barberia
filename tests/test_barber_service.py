from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.database.queries import barbers as barber_queries
from app.database.queries import profiles as profile_queries
from app.models.barber import BarberCreate, BarberCreateWithAccount
from app.services.barber_service import barber_service
from app.utils.errors import ValidationError


def test_create_barber_rejects_non_barbero_profile(monkeypatch):
    user_id = uuid4()
    payload = BarberCreate(
        user_id=user_id,
        full_name="Barbero Nuevo",
        email="barbero@demo.com",
    )

    monkeypatch.setattr(
        profile_queries,
        "get_profile",
        lambda *_: {"id": str(user_id), "role": "cliente", "active": True},
    )

    with pytest.raises(ValidationError):
        barber_service.create_barber(payload)


def test_create_barber_rejects_already_linked_user(monkeypatch):
    user_id = uuid4()
    payload = BarberCreate(
        user_id=user_id,
        full_name="Barbero Nuevo",
        email="barbero@demo.com",
    )

    monkeypatch.setattr(
        profile_queries,
        "get_profile",
        lambda *_: {"id": str(user_id), "role": "barbero", "active": True},
    )
    monkeypatch.setattr(
        barber_queries,
        "get_barber_by_user_id",
        lambda *_ , **__: {"id": str(uuid4()), "user_id": str(user_id)},
    )

    with pytest.raises(ValidationError):
        barber_service.create_barber(payload)


def test_create_barber_with_valid_user_link(monkeypatch):
    user_id = uuid4()
    barber_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    payload = BarberCreate(
        user_id=user_id,
        full_name="Barbero Nuevo",
        email="barbero@demo.com",
    )

    monkeypatch.setattr(
        profile_queries,
        "get_profile",
        lambda *_: {"id": str(user_id), "role": "barbero", "active": True},
    )
    monkeypatch.setattr(barber_queries, "get_barber_by_user_id", lambda *_ , **__: None)
    monkeypatch.setattr(
        barber_queries,
        "create_barber",
        lambda data: {
            "id": barber_id,
            "user_id": data["user_id"],
            "full_name": data["full_name"],
            "email": data.get("email"),
            "phone": None,
            "specialty": None,
            "bio": None,
            "avatar_url": None,
            "active": True,
            "created_at": now,
            "updated_at": now,
        },
    )

    result = barber_service.create_barber(payload)
    assert str(result.id) == barber_id
    assert str(result.user_id) == str(user_id)


def test_create_barber_with_account_success(monkeypatch):
    user_id = str(uuid4())
    barber_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    payload = BarberCreateWithAccount(
        full_name="Barbero Cuenta",
        email="barberocuenta@demo.com",
        password="secret123",
        specialty="Degradados",
    )

    class FakeAdmin:
        def create_user(self, _):
            class UserObj:
                id = user_id

            class Resp:
                user = UserObj()

            return Resp()

        def delete_user(self, _):
            return None

    class FakeAuth:
        admin = FakeAdmin()

    class FakeSupabase:
        auth = FakeAuth()

    monkeypatch.setattr("app.services.barber_service.get_supabase", lambda: FakeSupabase())
    monkeypatch.setattr(profile_queries, "get_profile", lambda *_: {"id": user_id, "role": "cliente", "active": True})
    monkeypatch.setattr(profile_queries, "update_profile_role", lambda *_: {"id": user_id, "role": "barbero"})
    monkeypatch.setattr(profile_queries, "update_profile", lambda *_: {"id": user_id})
    monkeypatch.setattr(
        barber_queries,
        "create_barber",
        lambda data: {
            "id": barber_id,
            "user_id": data["user_id"],
            "full_name": data["full_name"],
            "email": data.get("email"),
            "phone": None,
            "specialty": data.get("specialty"),
            "bio": None,
            "avatar_url": None,
            "active": True,
            "created_at": now,
            "updated_at": now,
        },
    )

    result = barber_service.create_barber_with_account(payload)

    assert str(result.id) == barber_id
    assert str(result.user_id) == user_id
    assert result.email == payload.email


def test_create_barber_with_account_rolls_back_auth_user_on_failure(monkeypatch):
    user_id = str(uuid4())
    payload = BarberCreateWithAccount(
        full_name="Barbero Fallo",
        email="fallo@demo.com",
        password="secret123",
    )
    deleted_ids = []

    class FakeAdmin:
        def create_user(self, _):
            class UserObj:
                id = user_id

            class Resp:
                user = UserObj()

            return Resp()

        def delete_user(self, target_user_id):
            deleted_ids.append(target_user_id)
            return None

    class FakeAuth:
        admin = FakeAdmin()

    class FakeSupabase:
        auth = FakeAuth()

    monkeypatch.setattr("app.services.barber_service.get_supabase", lambda: FakeSupabase())
    monkeypatch.setattr(profile_queries, "get_profile", lambda *_: {"id": user_id, "role": "cliente", "active": True})
    monkeypatch.setattr(profile_queries, "update_profile_role", lambda *_: {"id": user_id, "role": "barbero"})
    monkeypatch.setattr(profile_queries, "update_profile", lambda *_: {"id": user_id})
    monkeypatch.setattr(barber_queries, "create_barber", lambda *_: (_ for _ in ()).throw(Exception("db error")))

    with pytest.raises(ValidationError):
        barber_service.create_barber_with_account(payload)

    assert deleted_ids == [user_id]
