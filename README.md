# BarberWeb Backend (FastAPI + Supabase)

Backend REST para reservas de barberia con autenticacion JWT (Supabase), motor de disponibilidad por slots, modulo de reservas y OAuth de Google Calendar.

## Estado del proyecto

- Fase 1: Foundation (auth, servicios, barberos) - completa
- Fase 2.1: Disponibilidad (rules, breaks, days off) - completa
- Fase 2.2: Slots Engine - completa
- Fase 2.3: Bookings - completa
- Fase 3.1: Google Calendar OAuth (connect/callback/status/disconnect) - completa
- Pendiente: Fase 3.2 (sync de eventos), 3.3 (dashboard), 4 (hardening/deploy)

## Stack

- Python 3.11+
- FastAPI
- Supabase (PostgreSQL + Auth)
- PyJWT
- Cryptography (Fernet)
- Pytest

## Estructura principal

```txt
app/
  config.py
  main.py
  dependencies.py
  routers/
  services/
  models/
  database/
  utils/
sql/
tests/
```

## Requisitos

1. Python 3.11 o superior
2. Proyecto de Supabase activo
3. (Opcional para Calendar) Proyecto Google Cloud con OAuth Client

## Instalacion y ejecucion local

1) Crear y activar entorno virtual

```bash
python -m venv venv
venv/Scripts/activate
```

2) Instalar dependencias

```bash
pip install -r requirements-dev.txt
```

3) Configurar variables de entorno

```bash
copy .env.example .env
```

Rellena `.env` con tus valores reales.

4) Ejecutar servidor

```bash
venv/Scripts/uvicorn.exe app.main:app --reload
```

5) Abrir documentacion interactiva

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health: `http://127.0.0.1:8000/health`

Nota: `GET /` devuelve `404` por diseno (no hay ruta raiz).

## Variables de entorno

Referencia completa en `.env.example`.

### Supabase

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

### App

- `APP_ENV` (ej: `development`)
- `APP_PORT` (ej: `8000`)
- `CORS_ORIGINS` (ej: `http://localhost:5173`)

### Google Calendar OAuth

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` (ej: `http://localhost:8000/api/v1/calendar/callback`)
- `GOOGLE_SCOPES` (default: `https://www.googleapis.com/auth/calendar.events`)
- `GOOGLE_CALENDAR_ENABLED` (`true/false`)
- `TOKEN_ENCRYPTION_KEY` (clave Fernet base64)

Generar clave Fernet:

```bash
venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Negocio

- `BUSINESS_TIMEZONE` (ej: `America/Lima`)
- `MIN_BOOKING_ADVANCE_MINUTES` (ej: `30`)
- `MAX_BOOKING_ADVANCE_DAYS` (ej: `30`)

### Performance

- `DEFAULT_PAGE_SIZE` (ej: `50`)
- `MAX_PAGE_SIZE` (ej: `200`)
- `AUTH_CACHE_TTL_SECONDS` (ej: `30`)
- `AUTH_CACHE_MAX_ITEMS` (ej: `5000`)
- `QUERY_CACHE_TTL_SECONDS` (ej: `30`)
- `QUERY_CACHE_MAX_ITEMS` (ej: `5000`)

## Base de datos

- Migracion consolidada: `sql/000_ALL_MIGRATIONS.sql`
- Migracion adicional aplicada: `sql/008_breaks_no_overlap.sql`

## Tests

Ejecutar toda la suite:

```bash
venv/Scripts/python.exe -m pytest -q
```

E2E real contra Supabase (bookings):

```bash
PYTHONPATH=. venv/Scripts/python.exe tests/e2e_bookings_supabase.py
```

## Guía para frontend

La referencia de integracion endpoint por endpoint (auth, headers, request/response, ejemplos y flujo recomendado) esta en:

- `docs/FRONTEND_API_GUIDE.md`

El estado de avance, auditoria de gaps y orden recomendado de desarrollo esta en:

- `PROGRESO.md`

## Plan recomendado de ejecucion (resumen)

1. **P0 (inmediato):** congelar contrato API real y cerrar gaps de integracion frontend-backend (`/users`, `/settings/calendar`, `/stats`).
2. **P0 (inmediato):** cerrar flujo de alta y vinculacion de barbero (`auth.users` + `profiles.role='barbero'` + `barbers.user_id`).
3. **P1:** habilitar dashboard backend real y conectar frontend a metricas productivas.
4. **P2:** sincronizacion automatica con Google Calendar y hardening para produccion.

## Seguridad

- No subir `.env` al repositorio.
- Si expones accidentalmente secretos, rotarlos inmediatamente.
- `SUPABASE_SERVICE_ROLE_KEY` solo backend.
