from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.config import settings
from app.database.client import get_supabase
from app.dependencies import get_current_user
from app.main import app


def _assert_status(response, expected: int, step: str):
    if response.status_code != expected:
        raise AssertionError(f"{step} fallo ({response.status_code}): {response.text}")


def _iso_at(local_date, hour: int, minute: int, tz: ZoneInfo) -> str:
    return datetime(local_date.year, local_date.month, local_date.day, hour, minute, tzinfo=tz).isoformat()


def run_e2e():
    sb = get_supabase()
    client = TestClient(app)

    current_user = {"id": str(uuid4()), "role": "admin", "active": True}
    temp_auth_user_id = None

    def override_current_user():
        return current_user

    app.dependency_overrides[get_current_user] = override_current_user

    created_booking_ids = []
    created_break_ids = []
    created_day_off_dates = []
    created_barber_id = None
    created_service_id = None

    try:
        # Usuario real en auth.users para cumplir FKs (bookings.client_user_id y booking_history.changed_by)
        temp_email = f"e2e-bookings-{uuid4().hex[:10]}@example.com"
        created_user = sb.auth.admin.create_user(
            {
                "email": temp_email,
                "password": f"Tmp#{uuid4().hex[:10]}",
                "email_confirm": True,
                "user_metadata": {"full_name": "E2E User", "role": "cliente"},
            }
        )
        temp_auth_user_id = created_user.user.id
        current_user.update({"id": temp_auth_user_id})

        biz_tz = ZoneInfo(settings.BUSINESS_TIMEZONE)
        local_now = datetime.now(biz_tz)
        target_date = (local_now + timedelta(days=1)).date()

        # 1) Setup: servicio + barbero + relacion + disponibilidad
        service_payload = {
            "name": f"E2E Servicio {uuid4().hex[:8]}",
            "description": "Servicio temporal para pruebas E2E",
            "duration_minutes": 30,
            "price": 25.0,
            "category": "corte",
        }
        res_service = client.post("/api/v1/services", json=service_payload)
        _assert_status(res_service, 201, "Crear servicio")
        created_service_id = res_service.json()["id"]

        barber_payload = {
            "full_name": f"E2E Barber {uuid4().hex[:8]}",
            "email": f"e2e-{uuid4().hex[:6]}@example.com",
        }
        res_barber = client.post("/api/v1/barbers", json=barber_payload)
        _assert_status(res_barber, 201, "Crear barbero")
        created_barber_id = res_barber.json()["id"]

        res_assign = client.put(
            f"/api/v1/barbers/{created_barber_id}/services",
            json={"service_ids": [created_service_id]},
        )
        _assert_status(res_assign, 200, "Asignar servicio al barbero")

        res_rules = client.put(
            f"/api/v1/barbers/{created_barber_id}/availability",
            json={
                "rules": [
                    {
                        "day_of_week": target_date.isoweekday(),
                        "start_time": "09:00:00",
                        "end_time": "18:00:00",
                        "slot_interval_minutes": 30,
                    }
                ]
            },
        )
        _assert_status(res_rules, 200, "Crear regla de disponibilidad")

        # 2) Crear cuatro reservas en horarios distintos
        current_user.update({"role": "cliente"})

        start_complete = _iso_at(target_date, 10, 0, biz_tz)
        start_noshow = _iso_at(target_date, 11, 0, biz_tz)
        start_cancel = _iso_at(target_date, 12, 0, biz_tz)
        start_reschedule = _iso_at(target_date, 13, 0, biz_tz)
        new_start_reschedule = _iso_at(target_date, 14, 0, biz_tz)

        def create_booking(start_iso: str, key: str) -> str:
            payload = {
                "barber_id": created_barber_id,
                "service_id": created_service_id,
                "start_at": start_iso,
                "idempotency_key": key,
            }
            response = client.post("/api/v1/bookings", json=payload)
            _assert_status(response, 201, f"Crear booking {key}")
            booking_id = response.json()["id"]
            created_booking_ids.append(booking_id)
            return booking_id

        booking_complete = create_booking(start_complete, f"e2e-complete-{uuid4().hex[:8]}")
        booking_noshow = create_booking(start_noshow, f"e2e-noshow-{uuid4().hex[:8]}")
        booking_cancel = create_booking(start_cancel, f"e2e-cancel-{uuid4().hex[:8]}")
        booking_reschedule = create_booking(start_reschedule, f"e2e-resch-{uuid4().hex[:8]}")

        # 3) Confirmar/completar/no-show como admin
        current_user.update({"role": "admin"})

        res_confirm_1 = client.patch(f"/api/v1/bookings/{booking_complete}/confirm", json={})
        _assert_status(res_confirm_1, 200, "Confirmar booking completo")

        res_complete = client.patch(f"/api/v1/bookings/{booking_complete}/complete", json={})
        _assert_status(res_complete, 200, "Completar booking")
        assert res_complete.json()["status"] == "completed"

        res_confirm_2 = client.patch(f"/api/v1/bookings/{booking_noshow}/confirm", json={})
        _assert_status(res_confirm_2, 200, "Confirmar booking no-show")

        res_no_show = client.patch(f"/api/v1/bookings/{booking_noshow}/no-show", json={})
        _assert_status(res_no_show, 200, "Marcar booking no-show")
        assert res_no_show.json()["status"] == "no_show"

        # 4) Cancelar y reprogramar como cliente
        current_user.update({"role": "admin"})

        res_cancel = client.patch(
            f"/api/v1/bookings/{booking_cancel}/cancel",
            json={"reason": "Cancelacion E2E"},
        )
        _assert_status(res_cancel, 200, "Cancelar booking")
        assert res_cancel.json()["status"] == "cancelled"

        res_reschedule = client.patch(
            f"/api/v1/bookings/{booking_reschedule}/reschedule",
            json={"start_at": new_start_reschedule, "reason": "Reprogramacion E2E"},
        )
        _assert_status(res_reschedule, 200, "Reprogramar booking")
        rescheduled_start = datetime.fromisoformat(res_reschedule.json()["start_at"].replace("Z", "+00:00"))
        expected_start = datetime.fromisoformat(new_start_reschedule.replace("Z", "+00:00"))
        assert rescheduled_start == expected_start

        # 5) Verificar historial admin
        res_history = client.get(f"/api/v1/bookings/{booking_complete}/history")
        _assert_status(res_history, 200, "Historial booking")
        assert len(res_history.json()) >= 3  # pending, confirmed, completed

        print("[OK] E2E Bookings contra Supabase completado")
        print(f"  - completed: {booking_complete}")
        print(f"  - no_show:   {booking_noshow}")
        print(f"  - cancelled: {booking_cancel}")
        print(f"  - moved:     {booking_reschedule}")

    finally:
        # Limpieza de datos creados por prueba
        try:
            if created_booking_ids:
                sb.table("bookings").delete().in_("id", created_booking_ids).execute()
        except Exception:
            pass

        try:
            if created_day_off_dates and created_barber_id:
                for d in created_day_off_dates:
                    sb.table("day_off").delete().eq("barber_id", created_barber_id).eq("date", d).execute()
        except Exception:
            pass

        try:
            if created_break_ids:
                sb.table("breaks").delete().in_("id", created_break_ids).execute()
        except Exception:
            pass

        try:
            if created_barber_id:
                sb.table("availability_rules").delete().eq("barber_id", created_barber_id).execute()
                sb.table("barber_services").delete().eq("barber_id", created_barber_id).execute()
                sb.table("barbers").delete().eq("id", created_barber_id).execute()
        except Exception:
            pass

        try:
            if created_service_id:
                sb.table("services").delete().eq("id", created_service_id).execute()
        except Exception:
            pass

        try:
            if temp_auth_user_id:
                sb.auth.admin.delete_user(temp_auth_user_id)
        except Exception:
            pass

        app.dependency_overrides.clear()


if __name__ == "__main__":
    run_e2e()
