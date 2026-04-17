import sys
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_current_user
import uuid

client = TestClient(app)

# Bypass auth
def override_get_current_user():
    return {
        'id': str(uuid.uuid4()),
        'role': 'admin',
        'active': True
    }

app.dependency_overrides[get_current_user] = override_get_current_user

def run_tests():
    print("--- Test: Crear Barbero para Disponibilidad ---")
    res_b = client.post('/api/v1/barbers', json={
        'full_name': 'Test Availability Barber'
    })
    assert res_b.status_code == 201, res_b.text
    barber_id = res_b.json()['id']
    print(f"Barbero Creado OK. ID: {barber_id}")

    print("--- Test: Establecer Reglas Disponibilidad (PUT) ---")
    res_rules = client.put(f'/api/v1/barbers/{barber_id}/availability', json={
        "rules": [
            {
                "day_of_week": 1,
                "start_time": "09:00:00",
                "end_time": "18:00:00",
                "slot_interval_minutes": 30
            },
            {
                "day_of_week": 2,
                "start_time": "09:00:00",
                "end_time": "18:00:00",
                "slot_interval_minutes": 30
            }
        ]
    })
    assert res_rules.status_code == 200, res_rules.text
    print("Reglas Establecidas OK")

    print("--- Test: Agregar Break (POST) ---")
    res_break = client.post(f'/api/v1/barbers/{barber_id}/breaks', json={
        "day_of_week": 1,
        "start_time": "13:00:00",
        "end_time": "14:00:00",
        "description": "Almuerzo"
    })
    assert res_break.status_code == 201, res_break.text
    break_id = res_break.json()['id']
    print("Break Agregado OK")

    print("--- Test: Obtener Horario Completo (GET) ---")
    res_full = client.get(f'/api/v1/barbers/{barber_id}/availability')
    assert res_full.status_code == 200, res_full.text
    data = res_full.json()
    assert len(data['rules']) == 2
    assert len(data['breaks']) == 1
    print("Horario Completo Retornado OK")

    print("--- Test: Agregar Day Off (POST) ---")
    res_off = client.post(f'/api/v1/barbers/{barber_id}/days-off', json={
        "date": "2026-10-31",
        "reason": "Halloween"
    })
    assert res_off.status_code == 201, res_off.text
    print("Day Off Agregado OK")

    print("--- Test: Obtener Days Off (GET) ---")
    res_get_off = client.get(f'/api/v1/barbers/{barber_id}/days-off')
    assert res_get_off.status_code == 200, res_get_off.text
    assert len(res_get_off.json()) == 1
    print("Days off Retornados OK")

    print("=== TODOS LOS TESTS PASARON CON ÉXITO ===")

if __name__ == '__main__':
    run_tests()
