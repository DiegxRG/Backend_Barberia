# Guia de Integracion Frontend API v1

Guia practica para implementar consumo de endpoints del backend desde React (o cualquier frontend).

## 1) Convenciones generales

- Base URL local: `http://127.0.0.1:8000`
- Prefijo API: `/api/v1`
- Auth header: `Authorization: Bearer <access_token_supabase>`
- Formato de error estandar:

```json
{
  "detail": "Mensaje de error",
  "code": "ERROR_CODE",
  "timestamp": "2026-04-20T10:30:00+00:00"
}
```

Codigos frecuentes:

- `401 UNAUTHORIZED`: token invalido/expirado
- `403 FORBIDDEN`: rol sin permisos
- `404 NOT_FOUND`: recurso no existe
- `409 BOOKING_CONFLICT`: horario ya ocupado
- `422 BUSINESS_RULE_VIOLATION`: regla de negocio incumplida

## 2) Auth y perfiles

### `GET /api/v1/auth/me`

- Auth: cualquier usuario autenticado
- Uso frontend: cargar sesion inicial y rol

### `PATCH /api/v1/auth/profile`

- Auth: cualquier usuario autenticado
- Body parcial:

```json
{
  "full_name": "Diego",
  "phone": "+51999999999",
  "avatar_url": "https://..."
}
```

## 3) Servicios

### `GET /api/v1/services`

- Publico
- Query opcional: `include_inactive=true` (solo efectivo para admin autenticado)

### `GET /api/v1/services/{service_id}`

- Publico

### `POST /api/v1/services`

- Auth rol: `admin`

### `PATCH /api/v1/services/{service_id}`

- Auth rol: `admin`

### `DELETE /api/v1/services/{service_id}`

- Auth rol: `admin`
- Soft delete (`active=false`)

## 4) Barberos

### `GET /api/v1/barbers`

- Publico
- Query opcional: `include_inactive=true` (solo efectivo para admin autenticado)

### `GET /api/v1/barbers/{barber_id}`

- Publico
- Incluye servicios del barbero

### `POST /api/v1/barbers`

- Auth rol: `admin`

### `PATCH /api/v1/barbers/{barber_id}`

- Auth rol: `admin` o `barbero`

### `DELETE /api/v1/barbers/{barber_id}`

- Auth rol: `admin`
- Soft delete

### `PUT /api/v1/barbers/{barber_id}/services`

- Auth rol: `admin`
- Reemplaza lista completa

```json
{
  "service_ids": ["uuid-1", "uuid-2"]
}
```

## 5) Disponibilidad (rules, breaks, days-off)

### `GET /api/v1/barbers/{barber_id}/availability`

- Auth: usuario autenticado

### `PUT /api/v1/barbers/{barber_id}/availability`

- Auth rol: `admin` o `barbero`
- Reemplaza todas las reglas del barbero

```json
{
  "rules": [
    {
      "day_of_week": 1,
      "start_time": "09:00:00",
      "end_time": "18:00:00",
      "slot_interval_minutes": 30
    }
  ]
}
```

### `POST /api/v1/barbers/{barber_id}/breaks`

- Auth rol: `admin` o `barbero`

```json
{
  "day_of_week": 1,
  "start_time": "13:00:00",
  "end_time": "14:00:00",
  "description": "Almuerzo"
}
```

### `DELETE /api/v1/breaks/{break_id}`

- Auth rol: `admin` o `barbero`

### `GET /api/v1/barbers/{barber_id}/days-off`

- Auth: usuario autenticado
- Query opcional: `from_date=YYYY-MM-DD`

### `POST /api/v1/barbers/{barber_id}/days-off`

- Auth rol: `admin` o `barbero`

```json
{
  "date": "2026-12-24",
  "reason": "Descanso"
}
```

### `DELETE /api/v1/barbers/{barber_id}/days-off/{target_date}`

- Auth rol: `admin` o `barbero`

## 6) Slots (disponibilidad real)

### `GET /api/v1/slots`

- Auth: usuario autenticado
- Query requerida:
  - `barber_id` UUID
  - `service_id` UUID
  - `date` formato `YYYY-MM-DD`

Ejemplo:

`GET /api/v1/slots?barber_id=<uuid>&service_id=<uuid>&date=2026-04-20`

Respuesta:

```json
{
  "barber_id": "uuid",
  "service_id": "uuid",
  "date": "2026-04-20",
  "timezone": "America/Lima",
  "slots": [
    { "start": "09:00", "end": "09:30", "available": true }
  ]
}
```

## 7) Bookings

## 7.1 Crear reserva

### `POST /api/v1/bookings`

- Auth rol: `cliente` o `admin`
- Body:

```json
{
  "barber_id": "uuid",
  "service_id": "uuid",
  "start_at": "2026-04-20T09:00:00-05:00",
  "notes": "Corte degradado",
  "idempotency_key": "booking-20260420-0900-client01"
}
```

Reglas importantes:

- `start_at` debe incluir timezone
- valida ventana de anticipacion min/max
- valida slot disponible y no solapamiento
- `idempotency_key` evita doble reserva por reintento

## 7.2 Listar reservas

### `GET /api/v1/bookings`

- Auth: usuario autenticado
- Filtro por rol automatico:
  - `cliente`: solo propias
  - `barbero`: solo las de su agenda
  - `admin`: todas
- Query opcionales:
  - `status`
  - `from_date` (datetime ISO)
  - `to_date` (datetime ISO)

## 7.3 Detalle

### `GET /api/v1/bookings/{booking_id}`

- Auth: usuario autenticado (con validacion por rol)

## 7.4 Cancelar

### `PATCH /api/v1/bookings/{booking_id}/cancel`

- Auth rol: `cliente` (propia) o `admin`

```json
{
  "reason": "No podre asistir"
}
```

## 7.5 Reprogramar

### `PATCH /api/v1/bookings/{booking_id}/reschedule`

- Auth rol: `cliente` (propia) o `admin`

```json
{
  "start_at": "2026-04-20T10:00:00-05:00",
  "reason": "Cambio de hora"
}
```

## 7.6 Gestion operativa

### `PATCH /api/v1/bookings/{booking_id}/confirm`

- Auth rol: `barbero` o `admin`

### `PATCH /api/v1/bookings/{booking_id}/complete`

- Auth rol: `barbero` o `admin`

### `PATCH /api/v1/bookings/{booking_id}/no-show`

- Auth rol: `barbero` o `admin`

## 7.7 Historial

### `GET /api/v1/bookings/{booking_id}/history`

- Auth rol: `admin`

## 8) Google Calendar OAuth

### `GET /api/v1/calendar/connect`

- Auth rol: `admin` o `barbero`
- Respuesta: redireccion 302 a Google OAuth

### `GET /api/v1/calendar/callback?code=...&state=...`

- Publico (redirect)
- Guarda tokens cifrados en `google_calendar_tokens`

### `GET /api/v1/calendar/status`

- Auth rol: `admin` o `barbero`

### `DELETE /api/v1/calendar/disconnect`

- Auth rol: `admin` o `barbero`

## 9) Flujo recomendado en frontend

### Cliente (reserva)

1. Cargar servicios: `GET /services`
2. Cargar barberos: `GET /barbers`
3. Consultar slots: `GET /slots`
4. Reservar: `POST /bookings`
5. Ver mis reservas: `GET /bookings`

### Admin/barbero (operacion)

1. Configurar disponibilidad
2. Gestionar breaks y days off
3. Revisar reservas
4. Confirmar/completar/no-show
5. Conectar calendar y verificar estado

## 10) Tips de implementacion frontend

- Guardar `access_token` de Supabase y renovarlo segun flujo de Auth SDK.
- Incluir siempre `Authorization: Bearer ...` en endpoints protegidos.
- Mostrar mensaje de negocio cuando venga `code=BOOKING_CONFLICT`.
- En formularios de fecha/hora enviar siempre ISO con timezone (ej: `-05:00`).
- En reintentos de crear booking reutilizar el mismo `idempotency_key`.
