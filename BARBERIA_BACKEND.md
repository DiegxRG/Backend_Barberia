# Sistema de Reservas para Barbería - Backend

> Adaptado del "Sistema Pro de Reservas Inteligentes" con simplificaciones para entrega en 1 semana.
> Fecha: 2026-04-17

---

## 1) Resumen del Proyecto

- **Nombre**: Sistema de Reservas - Barbería
- **Objetivo**: Permitir a clientes reservar citas con barberos, gestionar servicios/horarios y operar la agenda diaria del negocio.
- **Plazo**: 1 semana (7 días)
- **Stack backend**: Python + FastAPI
- **Base de datos**: Supabase (PostgreSQL gestionado + Auth + Storage)
- **Frontend**: React (documentado aparte)

### 1.1 Estado Actual de Implementación (Repositorio)

- ✅ **Fase 1 completa**: Auth base, perfiles, servicios, barberos y disponibilidad inicial.
- ✅ **Fase 2.1 completa**: Reglas, breaks y days off con validaciones y pruebas.
- ✅ **Fase 2.2 completa**: Motor de slots activo en `GET /api/v1/slots`.
- ✅ **Fase 2.3 completa**: Módulo de bookings activo (crear/listar/detalle/cancelar/reprogramar/confirmar/completar/no-show/historial).
- ✅ **Fase 3.1 completa**: OAuth de Google Calendar (`connect`, `callback`, `status`, `disconnect`) con cifrado de tokens.
- 🔄 **Pendiente**: Fase 3.2 (sync de eventos desde booking_service), Fase 3.3 (dashboard), Fase 4 (hardening/deploy).

---

## 2) ¿Por qué FastAPI + Supabase?

### FastAPI
- Validación automática con Pydantic (ahorra tiempo en DTOs).
- Documentación Swagger/OpenAPI generada automáticamente.
- Async nativo = ideal para consultas a Supabase.
- Desarrollo más rápido que Flask para APIs REST.
- Manejo de errores y respuestas consistentes con menos código.

### Supabase
- PostgreSQL gestionado (sin configurar servidor de DB).
- **Auth integrado**: registro, login, recuperación de contraseña, login con Google/GitHub.
- Row Level Security (RLS) para seguridad a nivel de fila.
- Storage para imágenes (fotos de barberos, logo del negocio).
- Realtime para notificaciones (opcional pero útil).
- SDK oficial para Python (`supabase-py`).

---

## 3) Arquitectura Simplificada

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│          Consume API REST + Supabase Auth            │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP (JSON)
┌─────────────────▼───────────────────────────────────┐
│               Backend (FastAPI)                      │
│                                                      │
│  /api/v1/                                            │
│  ├── auth/        → registro, login (via Supabase)  │
│  ├── services/    → CRUD catálogo de servicios      │
│  ├── barbers/     → CRUD barberos + disponibilidad  │
│  ├── bookings/    → crear/cancelar/reprogramar      │
│  ├── slots/       → cálculo de disponibilidad       │
│  ├── calendar/    → Google Calendar OAuth + sync    │
│  └── dashboard/   → KPIs y estadísticas             │
│                                                      │
│  Capas internas (simple, sin hexagonal):             │
│  ├── routers/     → endpoints (controllers)          │
│  ├── services/    → lógica de negocio                │
│  ├── models/      → schemas Pydantic                 │
│  ├── database/    → cliente Supabase + queries       │
│  └── utils/       → helpers, validaciones            │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              Supabase (PostgreSQL)                    │
│  ├── Auth (usuarios + JWT + OAuth)                   │
│  ├── Database (tablas + RLS)                         │
│  └── Storage (imágenes)                              │
└─────────────────────────────────────────────────────┘
```

**Decisión**: No usar arquitectura hexagonal/DDD. Estructura plana por capas para velocidad de desarrollo.

---

## 4) Roles y Permisos (RBAC simplificado)

| Rol       | Descripción                              | Permisos principales                                        |
|-----------|------------------------------------------|--------------------------------------------------------------|
| `admin`   | Dueño/administrador de la barbería       | Todo: CRUD servicios, barberos, horarios, ver dashboard      |
| `barbero` | Empleado/barbero                         | Ver su agenda, confirmar/completar citas asignadas           |
| `cliente` | Cliente que reserva                      | Crear, consultar, cancelar y reprogramar sus propias citas   |

**Implementación**: Usar metadata de usuario en Supabase Auth (`user_metadata.role`) + validación en backend con dependencias de FastAPI.

---

## 5) Modelo de Datos (Supabase/PostgreSQL)

### 5.1 Tabla `profiles` (extiende Supabase Auth)
```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  full_name TEXT NOT NULL,
  phone TEXT,
  avatar_url TEXT,
  role TEXT NOT NULL DEFAULT 'cliente' CHECK (role IN ('admin', 'barbero', 'cliente')),
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 5.1.1 Trigger para creación automática de perfiles
Se requiere un trigger para crear el perfil automáticamente cuando un usuario se registra en Supabase Auth:

```sql
-- Función que crea perfil automáticamente
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, role, active)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
    COALESCE(NEW.raw_user_meta_data->>'role', 'cliente'),
    true
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger en auth.users
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

#### 5.1.2 Políticas RLS (Row Level Security)
```sql
-- Habilitar RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Política de lectura: usuarios ven su propio perfil
CREATE POLICY "Users can view own profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

-- Política de actualización: usuarios actualizan su propio perfil
CREATE POLICY "Users can update own profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

-- Política de inserción: se maneja automáticamente por el trigger
-- Para insert manual desde frontend (si fuera necesario):
CREATE POLICY "Users can insert own profile" ON profiles
  FOR INSERT WITH CHECK (auth.uid() = id);
```

> **Nota**: La inserción de perfiles se maneja automáticamente mediante el trigger `on_auth_user_created`. El frontend NO debe intentar insertar en la tabla `profiles` directamente.

### 5.2 Tabla `services` (catálogo de servicios)
```sql
CREATE TABLE services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
  price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
  category TEXT DEFAULT 'general',
  image_url TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Categorías sugeridas**: `corte`, `barba`, `combo`, `tratamiento`, `especial`

### 5.3 Tabla `barbers` (barberos del negocio)
```sql
CREATE TABLE barbers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  specialty TEXT,
  bio TEXT,
  avatar_url TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.4 Tabla `barber_services` (qué servicios ofrece cada barbero)
```sql
CREATE TABLE barber_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  UNIQUE(barber_id, service_id)
);
```

### 5.5 Tabla `availability_rules` (horario base semanal)

> **Convención `day_of_week`**: Se usa **ISO 8601** → `1=Lunes, 7=Domingo`.  
> En Python usar `date.isoweekday()` (NO `date.weekday()` que retorna 0=Lunes).  
> En PostgreSQL usar `EXTRACT(ISODOW FROM date)` (NO `EXTRACT(DOW ...)` que retorna 0=Domingo).  
> **Esta convención es obligatoria en TODO el sistema.**

```sql
CREATE TABLE availability_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  -- ISO 8601: 1=Lunes, 2=Martes, ..., 7=Domingo
  -- Python: date.isoweekday()  |  PostgreSQL: EXTRACT(ISODOW FROM date)
  day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  slot_interval_minutes INTEGER DEFAULT 30,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_time_range CHECK (start_time < end_time),
  UNIQUE(barber_id, day_of_week)
);
```

### 5.6 Tabla `breaks` (pausas/almuerzos por día)
```sql
CREATE TABLE breaks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  -- ISO 8601: 1=Lunes ... 7=Domingo (misma convención que availability_rules)
  day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  description TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_break_range CHECK (start_time < end_time),
  -- Prevenir breaks que se solapan entre sí para el mismo barbero y día
  EXCLUDE USING gist (
    barber_id WITH =,
    day_of_week WITH =,
    timerange(start_time, end_time) WITH &&
  )
);
```

> **Nota**: Un barbero puede tener múltiples breaks por día (ej: descanso mañana 10:30-10:45 + almuerzo 13:00-14:00), pero no se permite que se solapen entre sí.

### 5.7 Tabla `day_off` (días libres/vacaciones)
```sql
CREATE TABLE day_off (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(barber_id, date)
);
```

### 5.8 Tabla `bookings` (reservas)
```sql
CREATE TABLE bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_user_id UUID NOT NULL REFERENCES auth.users(id),
  barber_id UUID NOT NULL REFERENCES barbers(id),
  service_id UUID NOT NULL REFERENCES services(id),
  start_at TIMESTAMPTZ NOT NULL,
  end_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed', 'no_show')),
  notes TEXT,
  cancel_reason TEXT,
  idempotency_key TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Evitar doble reserva: no pueden solaparse citas del mismo barbero
  EXCLUDE USING gist (
    barber_id WITH =,
    tstzrange(start_at, end_at) WITH &&
  ) WHERE (status NOT IN ('cancelled'))
);

-- Índices para performance
CREATE INDEX idx_bookings_barber_date ON bookings(barber_id, start_at);
CREATE INDEX idx_bookings_client ON bookings(client_user_id, start_at);
CREATE INDEX idx_bookings_status ON bookings(status);
```

### 5.9 Tabla `booking_history` (historial de cambios)
```sql
CREATE TABLE booking_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  previous_status TEXT,
  new_status TEXT NOT NULL,
  changed_by UUID REFERENCES auth.users(id),
  reason TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6) Endpoints API (v1)

### 6.1 Auth (delegado a Supabase)
El frontend interactúa directamente con Supabase Auth SDK. El backend solo valida JWT.

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/auth/me` | Perfil del usuario autenticado | Sí |
| `PATCH` | `/api/v1/auth/profile` | Actualizar perfil propio | Sí |

### 6.2 Servicios (Catálogo)
| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `GET` | `/api/v1/services` | Listar servicios activos | Público |
| `GET` | `/api/v1/services/{id}` | Detalle de servicio | Público |
| `POST` | `/api/v1/services` | Crear servicio | admin |
| `PUT` | `/api/v1/services/{id}` | Editar servicio | admin |
| `DELETE` | `/api/v1/services/{id}` | Desactivar servicio | admin |

### 6.3 Barberos
| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `GET` | `/api/v1/barbers` | Listar barberos activos | Público |
| `GET` | `/api/v1/barbers/{id}` | Detalle de barbero | Público |
| `POST` | `/api/v1/barbers` | Registrar barbero | admin |
| `PUT` | `/api/v1/barbers/{id}` | Editar barbero | admin |
| `DELETE` | `/api/v1/barbers/{id}` | Desactivar barbero | admin |

### 6.4 Disponibilidad / Horarios
| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `GET` | `/api/v1/barbers/{id}/availability` | Horario semanal del barbero | Autenticado |
| `PUT` | `/api/v1/barbers/{id}/availability` | Configurar horario semanal | admin |
| `GET` | `/api/v1/barbers/{id}/breaks` | Listar breaks | admin |
| `POST` | `/api/v1/barbers/{id}/breaks` | Crear break | admin |
| `DELETE` | `/api/v1/breaks/{id}` | Eliminar break | admin |
| `GET` | `/api/v1/barbers/{id}/days-off` | Listar días libres | admin |
| `POST` | `/api/v1/barbers/{id}/days-off` | Crear día libre | admin |
| `DELETE` | `/api/v1/days-off/{id}` | Eliminar día libre | admin |

### 6.5 Slots Disponibles (Motor de disponibilidad)
> **Idea clave adaptada del sistema original**: cálculo real de slots considerando horarios, breaks, días libres y reservas existentes.

| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `GET` | `/api/v1/slots` | Slots disponibles | Autenticado |

**Query params**:
- `barber_id` (UUID, requerido)
- `service_id` (UUID, requerido)
- `date` (YYYY-MM-DD, requerido)

**Respuesta ejemplo**:
```json
{
  "barber_id": "uuid",
  "service_id": "uuid",
  "date": "2026-04-20",
  "slots": [
    { "start": "09:00", "end": "09:30", "available": true },
    { "start": "09:30", "end": "10:00", "available": true },
    { "start": "10:00", "end": "10:30", "available": false },
    { "start": "10:30", "end": "11:00", "available": true }
  ]
}
```

**Lógica del motor de slots** (adaptada del Sprint 3 del sistema original):
1. Obtener `availability_rule` del barbero para el `day_of_week` de la fecha.
2. Generar slots base según `slot_interval_minutes` y duración del servicio.
3. Filtrar slots que caen en `breaks`.
4. Verificar si la fecha es `day_off` → retornar vacío.
5. Restar slots ocupados por `bookings` activas (pending/confirmed).
6. Marcar como `available: true/false`.

### 6.6 Reservas (Bookings)
| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `POST` | `/api/v1/bookings` | Crear reserva | cliente, admin |
| `GET` | `/api/v1/bookings` | Listar reservas (filtrado por rol) | Autenticado |
| `GET` | `/api/v1/bookings/{id}` | Detalle de reserva | Autenticado |
| `PATCH` | `/api/v1/bookings/{id}/cancel` | Cancelar reserva | cliente (propia), admin |
| `PATCH` | `/api/v1/bookings/{id}/reschedule` | Reprogramar | cliente (propia), admin |
| `PATCH` | `/api/v1/bookings/{id}/confirm` | Confirmar cita | barbero, admin |
| `PATCH` | `/api/v1/bookings/{id}/complete` | Marcar completada | barbero, admin |
| `PATCH` | `/api/v1/bookings/{id}/no-show` | Marcar no-show | barbero, admin |
| `GET` | `/api/v1/bookings/{id}/history` | Historial de la reserva | admin |

**Request crear reserva**:
```json
{
  "barber_id": "uuid",
  "service_id": "uuid",
  "start_at": "2026-04-20T09:00:00-05:00",
  "notes": "Corte con degradado",
  "idempotency_key": "booking-20260420-0900-client01"
}
```

**Reglas de negocio (adaptadas del sistema original)**:
- `end_at` se calcula automáticamente: `start_at + service.duration_minutes`.
- Validación de solapamiento antes de crear.
- `idempotency_key` para evitar doble reserva por reintento.
- Política de ventana: mínimo 30 min de anticipación, máximo 30 días.
- Al cancelar/reprogramar se registra en `booking_history`.

### 6.7 Google Calendar (OAuth + API real)
> **Idea del sistema original**: Sincronización bidireccional con Google Calendar del Sprint 6.

| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `GET` | `/api/v1/calendar/connect` | Iniciar flujo OAuth con Google | admin, barbero |
| `GET` | `/api/v1/calendar/callback` | Callback de Google OAuth (recibe code) | Público (redirect) |
| `GET` | `/api/v1/calendar/status` | Ver si el usuario tiene Calendar conectado | admin, barbero |
| `DELETE` | `/api/v1/calendar/disconnect` | Revocar acceso a Google Calendar | admin, barbero |

**Flujo OAuth**:
```
1. Admin/barbero hace click en "Conectar Google Calendar"
2. Frontend redirige a GET /api/v1/calendar/connect
3. Backend genera URL de consentimiento de Google y redirige
4. Usuario aprueba permisos en Google
5. Google redirige a GET /api/v1/calendar/callback?code=xxx
6. Backend intercambia code por access_token + refresh_token
7. Tokens se guardan cifrados en tabla google_calendar_tokens
8. Redirige al frontend con status=success
```

**Sincronización automática** (en booking_service):
- Al **crear/confirmar** reserva → Crear evento en Google Calendar del barbero
- Al **cancelar** reserva → Eliminar evento de Google Calendar
- Al **reprogramar** reserva → Actualizar fecha/hora del evento
- Evento incluye: nombre del cliente, servicio, hora, notas

**Tabla adicional**: `google_calendar_tokens`
```sql
CREATE TABLE google_calendar_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  token_expires_at TIMESTAMPTZ NOT NULL,
  calendar_id TEXT DEFAULT 'primary',
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id)
);
```

### 6.8 Dashboard
| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| `GET` | `/api/v1/dashboard/stats` | KPIs del día/semana/mes | admin |
| `GET` | `/api/v1/dashboard/upcoming` | Próximas citas del día | admin, barbero |

**Stats incluye**:
- Total citas de hoy / esta semana / este mes
- Tasa de cancelación
- Barbero más solicitado
- Servicio más popular
- Ingresos estimados

---

## 7) Estructura del Proyecto

```
barberia-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + CORS + routers
│   ├── config.py                # Settings (Supabase URL, keys, etc.)
│   ├── dependencies.py          # Auth dependency (verify JWT)
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # /auth/me, /auth/profile
│   │   ├── services.py          # CRUD servicios
│   │   ├── barbers.py           # CRUD barberos + disponibilidad
│   │   ├── slots.py             # Cálculo de slots
│   │   ├── bookings.py          # Reservas
│   │   ├── calendar.py          # Google Calendar OAuth + sync
│   │   └── dashboard.py         # Estadísticas
│   │
│   ├── services/                # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── service_service.py
│   │   ├── barber_service.py
│   │   ├── slot_engine.py       # Motor de slots (core)
│   │   ├── booking_service.py
│   │   ├── calendar_service.py  # Google Calendar API integration
│   │   └── dashboard_service.py
│   │
│   ├── models/                  # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── service.py
│   │   ├── barber.py
│   │   ├── slot.py
│   │   ├── booking.py
│   │   ├── calendar.py
│   │   └── dashboard.py
│   │
│   ├── database/                # Supabase client + queries
│   │   ├── __init__.py
│   │   ├── client.py            # Supabase client singleton
│   │   └── queries/
│   │       ├── services.py
│   │       ├── barbers.py
│   │       ├── bookings.py
│   │       ├── availability.py
│   │       └── calendar.py      # Queries de tokens de Calendar
│   │
│   └── utils/
│       ├── __init__.py
│       ├── errors.py            # Excepciones custom + handlers
│       └── timezone.py          # Helpers de zona horaria
│
├── .env.example
├── requirements.txt
├── README.md
└── Dockerfile (opcional)
```

---

## 8) Configuración y Variables de Entorno

```env
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...    # Solo para operaciones admin del backend
SUPABASE_JWT_SECRET=your-jwt-secret        # Para verificar tokens

# App
APP_ENV=development
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173

# Google Calendar OAuth
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxx
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/calendar/callback
GOOGLE_SCOPES=https://www.googleapis.com/auth/calendar.events

# Negocio
BUSINESS_TIMEZONE=America/Lima
MIN_BOOKING_ADVANCE_MINUTES=30
MAX_BOOKING_ADVANCE_DAYS=30
```

---

## 9) Autenticación y Seguridad

### Flujo de Auth
```
1. Cliente se registra/logea via Supabase Auth SDK (en frontend).
2. Frontend recibe JWT de Supabase.
3. Frontend envía JWT en header: Authorization: Bearer <token>
4. Backend verifica JWT con Supabase JWT Secret.
5. Backend extrae user_id y rol del token.
6. Dependencia de FastAPI (Depends) inyecta usuario autenticado en cada endpoint.
```

### Dependency de Auth (FastAPI)
```python
# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verifica JWT de Supabase y retorna datos del usuario."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
        user_id = payload.get("sub")
        # Consultar perfil en profiles table
        profile = await get_profile(user_id)
        return profile
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def require_role(*roles):
    """Decorator para verificar rol del usuario."""
    async def role_checker(user = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="No tienes permisos")
        return user
    return role_checker
```

---

## 10) Motor de Slots - Algoritmo

> Idea central tomada del Sprint 3 del sistema original.

### 10.1 Manejo de Zona Horaria (CRÍTICO)

> **Regla de oro**: La DB almacena `TIMESTAMPTZ` (UTC). Las `availability_rules` y `breaks` usan `TIME` (hora local del negocio). El motor de slots opera en **hora local del negocio** y solo convierte a UTC al comparar con bookings.

```python
# app/utils/timezone.py

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from app.config import settings

BUSINESS_TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)  # ej: "America/Lima"
UTC_TZ = ZoneInfo("UTC")

def to_business_tz(dt_utc: datetime) -> datetime:
    """Convierte datetime UTC a zona horaria del negocio."""
    return dt_utc.astimezone(BUSINESS_TZ)

def to_utc(dt_local: datetime) -> datetime:
    """Convierte datetime local del negocio a UTC."""
    return dt_local.astimezone(UTC_TZ)

def make_local_datetime(local_date: date, local_time: time) -> datetime:
    """Combina fecha + hora local en un datetime con zona horaria del negocio."""
    naive = datetime.combine(local_date, local_time)
    return naive.replace(tzinfo=BUSINESS_TZ)
```

### 10.2 Algoritmo Principal

```python
# app/services/slot_engine.py

from datetime import date, time, datetime, timedelta
from app.utils.timezone import BUSINESS_TZ, UTC_TZ, to_business_tz, to_utc, make_local_datetime

def calculate_available_slots(barber_id: str, service_id: str, target_date: date) -> list:
    """
    Calcula slots disponibles reales para un barbero en una fecha.

    CONVENCIÓN day_of_week: ISO 8601 → 1=Lunes, 7=Domingo
    Usar date.isoweekday() en TODO el código Python.

    Pasos:
    1. Obtener availability_rule del barbero para el día de la semana (ISO).
    2. Si no hay regla o está inactiva → sin disponibilidad.
    3. Verificar day_off para esa fecha → sin disponibilidad.
    4. Generar slots base: desde start_time hasta end_time, considerando
       que el último slot debe terminar ANTES de end_time.
    5. Filtrar slots cuyo RANGO COMPLETO (start → start+duración) choca con breaks.
    6. Filtrar slots ocupados por bookings existentes (pending/confirmed),
       comparando en UTC para consistencia con la DB.
    7. Retornar lista de slots con flag available.
    """

    # Obtener duración del servicio
    service = get_service(service_id)
    duration = timedelta(minutes=service.duration_minutes)

    # 1. Regla de disponibilidad — USAR isoweekday() (1=Lunes, 7=Domingo)
    iso_dow = target_date.isoweekday()  # ⚠️ NO usar .weekday() (0=Monday)
    rule = get_availability_rule(barber_id, iso_dow)
    if not rule or not rule.active:
        return []

    # 2. Día libre
    if is_day_off(barber_id, target_date):
        return []

    # 3. Generar slots base (en hora local del negocio)
    slots = generate_time_slots(
        rule_start=rule.start_time,
        rule_end=rule.end_time,
        service_duration=duration,
        interval=timedelta(minutes=rule.slot_interval_minutes),
        target_date=target_date
    )

    # 4. Filtrar breaks — con awareness de duración del servicio
    breaks = get_breaks(barber_id, iso_dow)
    slots = [s for s in slots if not slot_overlaps_any_break(s, duration, breaks)]

    # 5. Filtrar bookings existentes — convertir a UTC para comparar con DB
    #    Ventana de búsqueda: inicio del día hasta fin del día EN ZONA LOCAL
    day_start_utc = to_utc(make_local_datetime(target_date, time(0, 0)))
    day_end_utc = to_utc(make_local_datetime(target_date, time(23, 59, 59)))
    active_bookings = get_active_bookings(barber_id, day_start_utc, day_end_utc)

    slots = mark_availability(slots, duration, active_bookings)

    return slots
```

### 10.3 Funciones Helper

```python
def generate_time_slots(rule_start, rule_end, service_duration, interval, target_date):
    """
    Genera slots base desde rule_start hasta rule_end.
    El último slot DEBE terminar antes o justo a rule_end.

    Ejemplo: regla 09:00-18:00, servicio 45min, intervalo 30min
    → 09:00, 09:30, 10:00, ..., 17:00 (17:00+45min=17:45 ≤ 18:00 ✓)
    → NO incluye 17:30 (17:30+45min=18:15 > 18:00 ✗)
    """
    slots = []
    current = make_local_datetime(target_date, rule_start)
    end_limit = make_local_datetime(target_date, rule_end)

    while current + service_duration <= end_limit:
        slots.append({"start": current, "end": current + service_duration, "available": True})
        current += interval

    return slots


def slot_overlaps_any_break(slot, service_duration, breaks):
    """
    Verifica si el RANGO COMPLETO del slot (slot.start → slot.start + duración)
    se solapa con algún break.

    ⚠️ IMPORTANTE: No solo verificar si slot.start cae en el break,
    sino si el servicio COMPLETO choca con el break.

    Ejemplo: Break 12:00-13:00, servicio 60min.
    - Slot 11:00 → servicio termina 12:00 → NO choca (justo al borde) ✓
    - Slot 11:30 → servicio termina 12:30 → SÍ choca ✗
    - Slot 13:00 → servicio termina 14:00 → NO choca ✓
    """
    slot_start = slot["start"]
    slot_end = slot["end"]  # ya calculado como start + duration

    for brk in breaks:
        brk_start = make_local_datetime(slot_start.date(), brk.start_time)
        brk_end = make_local_datetime(slot_start.date(), brk.end_time)

        # Solapamiento: [slot_start, slot_end) ∩ [brk_start, brk_end) ≠ ∅
        if slot_start < brk_end and slot_end > brk_start:
            return True

    return False


def mark_availability(slots, service_duration, active_bookings):
    """
    Marca cada slot como available/unavailable basado en bookings existentes.
    Las bookings vienen en UTC desde la DB → se convierten a zona local para comparar.
    """
    for slot in slots:
        slot_start = slot["start"]
        slot_end = slot["end"]

        for booking in active_bookings:
            # Convertir booking de UTC a hora local del negocio
            bk_start_local = to_business_tz(booking.start_at)
            bk_end_local = to_business_tz(booking.end_at)

            # Solapamiento: [slot_start, slot_end) ∩ [bk_start, bk_end) ≠ ∅
            if slot_start < bk_end_local and slot_end > bk_start_local:
                slot["available"] = False
                break

    return slots
```

### 10.4 Respuesta del Endpoint

```python
# En el router, convertir los datetimes a strings para la respuesta JSON
def format_slots_response(barber_id, service_id, target_date, slots):
    return {
        "barber_id": barber_id,
        "service_id": service_id,
        "date": target_date.isoformat(),
        "timezone": settings.BUSINESS_TIMEZONE,
        "slots": [
            {
                "start": slot["start"].strftime("%H:%M"),
                "end": slot["end"].strftime("%H:%M"),
                "available": slot["available"]
            }
            for slot in slots
        ]
    }
```

---

## 11) Plan de Ejecución - 7 días

> **Estrategia de testing**: Tests unitarios se escriben en PARALELO con cada feature, no al final.  
> **Google Calendar**: Setup de Google Cloud Console se hace Día 1 (aprovechando tiempos de espera de Supabase setup). Implementación OAuth en Día 5.

### Día 1: Setup + Auth + DB + Google Cloud Config
- Crear proyecto FastAPI + estructura de carpetas.
- Configurar Supabase (proyecto, tablas con migraciones SQL, auth).
- Implementar `app/utils/timezone.py` con helpers de zona horaria.
- Implementar dependency de auth (`get_current_user`, `require_role`).
- Endpoint `/auth/me` funcional.
- **Google Cloud**: Crear proyecto, habilitar Calendar API, configurar OAuth consent screen y credentials. *(Esto toma ~20 min y se hace mientras Supabase crea tablas)*.
- Crear tabla `google_calendar_tokens` en la migración SQL.
- ✅ **Test**: Verificar auth dependency con tokens válidos/inválidos/expirados.

### Día 2: Servicios + Barberos
- CRUD completo de servicios (con categorías de barbería).
- CRUD completo de barberos.
- Relación barbero-servicios (tabla pivot + endpoint `GET /services/{id}/barbers`).
- Validaciones con Pydantic.
- ✅ **Test**: CRUD operations + validaciones de permisos RBAC.

### Día 3: Disponibilidad + Motor de Slots
- CRUD de horarios semanales (`availability_rules`, convención ISO `day_of_week`).
- CRUD de breaks (con constraint de no-solapamiento).
- CRUD de días libres.
- **Motor de slots** (core del sistema) — con manejo explícito de timezone.
- Endpoint `/slots` funcional.
- ✅ **Test**: Suite completa del motor de slots (ver Sección 16).

### Día 4: Reservas (Core)
- Crear reserva con validaciones (ventana min/max, slot disponible).
- Cancelar + reprogramar con historial.
- Confirmar + completar + no-show.
- Idempotencia con `idempotency_key`.
- ✅ **Test**: Flujo completo de reserva, doble booking, cancelación.

### Día 5: Google Calendar OAuth + Sync
- Flujo OAuth completo: `connect` → consent → `callback` → guardar tokens cifrados.
- Endpoint de `status` y `disconnect`.
- Integración con booking_service: al crear/confirmar → crear evento Calendar.
- Al cancelar → eliminar evento. Al reprogramar → actualizar evento.
- Refresh automático de tokens expirados.
- ✅ **Test**: Mock de Google API + flujo OAuth con tokens simulados.

### Día 6: Dashboard + Testing de Integración
- Endpoint de estadísticas (KPIs del día/semana/mes).
- Próximas citas del día.
- Filtros en listados (por fecha, por barbero, por estado).
- **Testing de integración**: flujos completos end-to-end via TestClient.
- RBAC completo validado en TODOS los endpoints.
- ✅ **Test**: Tests de integración con Supabase de testing.

### Día 7: Deploy + Documentación + Hardening
- Deploy backend (Railway / Render / Fly.io).
- Manejo de errores robusto (todos los códigos de la Sección 12).
- CORS configurado para producción.
- Rate limiting en endpoints sensibles (`/bookings`, `/auth`).
- Pruebas de integración frontend-backend.
- Documentación Swagger revisada y completa.
- Ajustes finales.

---

## 12) Formato de Error Estándar

```json
{
  "detail": "No tienes permisos para esta acción",
  "code": "FORBIDDEN",
  "timestamp": "2026-04-20T10:30:00-05:00"
}
```

Códigos comunes:
| HTTP | Código interno | Descripción |
|------|---------------|-------------|
| 400 | `VALIDATION_ERROR` | Datos de entrada inválidos |
| 401 | `UNAUTHORIZED` | Token inválido o expirado |
| 403 | `FORBIDDEN` | Sin permisos para la acción |
| 404 | `NOT_FOUND` | Recurso no encontrado |
| 409 | `BOOKING_CONFLICT` | Slot ya ocupado / reserva duplicada |
| 422 | `BUSINESS_RULE_VIOLATION` | Regla de negocio violada |
| 500 | `INTERNAL_ERROR` | Error interno del servidor |

---

## 13) Ideas Aprovechadas del Sistema Original

| Idea del Sistema Pro | Adaptación para Barbería |
|---------------------|--------------------------|
| Motor de slots con availability_rules + breaks + time_off + holidays + bookings | ✅ Mantenido completo (core del sistema) |
| Idempotency key en creación de reservas | ✅ Mantenido (evita doble booking por reintento) |
| Historial de estados (booking_status_history) | ✅ Simplificado como booking_history |
| Catálogo de servicios con duración y precio | ✅ Mantenido + categorías de barbería |
| Validación de solapamiento (EXCLUDE constraint) | ✅ Mantenido a nivel DB |
| Política de ventana de reserva (min/max anticipación) | ✅ 30 min mínimo / 30 días máximo |
| RBAC estricto por endpoint | ✅ Simplificado a 3 roles |
| Arquitectura hexagonal + DDD | ❌ Reemplazado por estructura plana por capas (más rápido en Python) |
| Multi-tenant / locations | ❌ No necesario para 1 barbería |
| IA / RAG / pgvector | ❌ Fuera de alcance |
| Google Calendar sync (OAuth + API real) | ✅ Incluido: crear/editar/eliminar eventos al cambiar estado de reserva |
| WhatsApp Cloud API | ❌ Fuera de alcance |
| Gmail API | ❌ Fuera de alcance |

---

## 14) Dependencias (requirements.txt)

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
supabase==2.9.0
python-dotenv==1.0.1
pydantic[email]==2.9.0
pydantic-settings==2.5.0
PyJWT==2.9.0
python-dateutil==2.9.0
httpx==0.27.0
google-auth==2.34.0
google-auth-oauthlib==1.2.1
google-api-python-client==2.149.0
cryptography==43.0.0
```

### 14.1 Dependencias de Desarrollo (requirements-dev.txt)

```txt
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-cov==5.0.0
httpx==0.27.0           # TestClient de FastAPI usa httpx
faker==28.0.0           # Datos de prueba realistas
freezegun==1.3.1        # Mock de datetime para tests de slots/timezone
```

---

## 15) Notas Finales

- **Zona horaria**:
  - Supabase almacena `TIMESTAMPTZ` en UTC.
  - Las tablas `availability_rules` y `breaks` usan `TIME` (hora local del negocio).
  - El motor de slots opera en **hora local del negocio** (`BUSINESS_TIMEZONE`).
  - La conversión UTC ↔ local se hace con `zoneinfo.ZoneInfo` (ver `app/utils/timezone.py`).
  - El frontend envía `start_at` con offset (`2026-04-20T09:00:00-05:00`) y el backend lo convierte.
- **Convención `day_of_week`**: ISO 8601 → `1=Lunes, 7=Domingo`.
  - Python: `date.isoweekday()` (⚠️ NO `date.weekday()`).
  - PostgreSQL: `EXTRACT(ISODOW FROM date)` (⚠️ NO `EXTRACT(DOW ...)`).
- **Soft delete**: Servicios y barberos usan flag `active` en vez de borrado físico.
- **CORS**: Configurado para aceptar requests del frontend en desarrollo (`localhost:5173`). En producción, restringir al dominio real.
- **Google Calendar**: Los tokens OAuth se almacenan cifrados con `cryptography.fernet`. Se hace refresh automático cuando el access_token expira. Si el usuario revoca acceso desde Google, se captura el error `invalid_grant` y se desconecta gracefully.
- **Escalabilidad futura**: Si el proyecto crece, se puede:
  - Agregar notificaciones por email/WhatsApp.
  - Agregar módulo de pagos.
  - Convertir a multi-tenant (múltiples barberías).
  - Agregar IA para sugerencias de horarios.

---

## 16) Tests Automatizados - Motor de Slots

> El motor de slots es el componente más crítico. Debe tener cobertura mínima del 90%.

### 16.1 Estructura de Tests

```
tests/
├── test_consistency_fixes.py     # RBAC / hardening de endpoints base
├── test_slot_service.py          # Tests del motor de slots
├── test_slots_router.py          # Tests del endpoint /slots
├── test_booking_service.py       # Reglas de negocio de bookings
├── test_bookings_router.py       # Tests de endpoints de reservas
├── test_calendar_service.py      # OAuth service de Google Calendar
├── test_calendar_router.py       # Endpoints calendar
└── e2e_bookings_supabase.py      # Flujo real E2E contra Supabase
```

### 16.2 Fixtures (`conftest.py`)

```python
import pytest
from datetime import date, time, timedelta
from dataclasses import dataclass

@dataclass
class MockRule:
    start_time: time
    end_time: time
    slot_interval_minutes: int
    active: bool

@dataclass
class MockBreak:
    start_time: time
    end_time: time

@dataclass
class MockBooking:
    start_at: 'datetime'  # UTC
    end_at: 'datetime'    # UTC

@dataclass
class MockService:
    duration_minutes: int

@pytest.fixture
def standard_rule():
    """Horario estándar: 09:00-18:00, intervalos de 30 min."""
    return MockRule(
        start_time=time(9, 0),
        end_time=time(18, 0),
        slot_interval_minutes=30,
        active=True
    )

@pytest.fixture
def lunch_break():
    """Break de almuerzo: 13:00-14:00."""
    return MockBreak(start_time=time(13, 0), end_time=time(14, 0))

@pytest.fixture
def service_30min():
    return MockService(duration_minutes=30)

@pytest.fixture
def service_60min():
    return MockService(duration_minutes=60)

@pytest.fixture
def service_45min():
    return MockService(duration_minutes=45)
```

### 16.3 Tests del Motor de Slots (`test_slot_engine.py`)

```python
import pytest
from datetime import date, time, datetime, timedelta
from zoneinfo import ZoneInfo
from freezegun import freeze_time

BIZ_TZ = ZoneInfo("America/Lima")  # UTC-5
UTC = ZoneInfo("UTC")


class TestGenerateTimeSlots:
    """Tests para la generación de slots base."""

    def test_basic_slots_30min_service(self, standard_rule, service_30min):
        """09:00-18:00 con servicio de 30min → 18 slots."""
        slots = generate_time_slots(
            rule_start=time(9, 0),
            rule_end=time(18, 0),
            service_duration=timedelta(minutes=30),
            interval=timedelta(minutes=30),
            target_date=date(2026, 4, 20)
        )
        assert len(slots) == 18
        assert slots[0]["start"].hour == 9
        assert slots[0]["start"].minute == 0
        assert slots[-1]["start"].hour == 17
        assert slots[-1]["start"].minute == 30
        # Último slot: 17:30 + 30min = 18:00 ≤ 18:00 ✓

    def test_60min_service_reduces_slots(self, standard_rule, service_60min):
        """09:00-18:00 con servicio de 60min → último slot a las 17:00."""
        slots = generate_time_slots(
            rule_start=time(9, 0),
            rule_end=time(18, 0),
            service_duration=timedelta(minutes=60),
            interval=timedelta(minutes=30),
            target_date=date(2026, 4, 20)
        )
        last_slot = slots[-1]
        assert last_slot["start"].hour == 17
        assert last_slot["start"].minute == 0
        # 17:00 + 60min = 18:00 ≤ 18:00 ✓
        # NO debe existir slot 17:30 (17:30+60=18:30 > 18:00)
        assert not any(s["start"].hour == 17 and s["start"].minute == 30 for s in slots)

    def test_45min_service_30min_interval(self):
        """09:00-12:00 con servicio de 45min, intervalo 30min.
        Slots: 09:00(→09:45), 09:30(→10:15), 10:00(→10:45),
               10:30(→11:15), 11:00(→11:45)
        NO incluye 11:30 (11:30+45=12:15 > 12:00)
        """
        slots = generate_time_slots(
            rule_start=time(9, 0),
            rule_end=time(12, 0),
            service_duration=timedelta(minutes=45),
            interval=timedelta(minutes=30),
            target_date=date(2026, 4, 20)
        )
        assert len(slots) == 5
        assert slots[-1]["start"].hour == 11
        assert slots[-1]["start"].minute == 0

    def test_empty_when_service_longer_than_window(self):
        """Ventana 09:00-09:30, servicio 60min → 0 slots."""
        slots = generate_time_slots(
            rule_start=time(9, 0),
            rule_end=time(9, 30),
            service_duration=timedelta(minutes=60),
            interval=timedelta(minutes=30),
            target_date=date(2026, 4, 20)
        )
        assert len(slots) == 0


class TestBreakOverlap:
    """Tests para filtrado de breaks con duración de servicio."""

    def test_slot_before_break_no_overlap(self, lunch_break):
        """Slot 12:00, servicio 60min → termina 13:00 = borde del break → NO choca."""
        slot = {"start": _make_dt(12, 0), "end": _make_dt(13, 0)}
        assert not slot_overlaps_any_break(slot, timedelta(minutes=60), [lunch_break])

    def test_slot_overlaps_break_due_to_duration(self, lunch_break):
        """Slot 12:30, servicio 60min → termina 13:30 → SÍ choca con break 13:00-14:00."""
        slot = {"start": _make_dt(12, 30), "end": _make_dt(13, 30)}
        assert slot_overlaps_any_break(slot, timedelta(minutes=60), [lunch_break])

    def test_slot_during_break(self, lunch_break):
        """Slot 13:15, servicio 30min → SÍ choca (dentro del break)."""
        slot = {"start": _make_dt(13, 15), "end": _make_dt(13, 45)}
        assert slot_overlaps_any_break(slot, timedelta(minutes=30), [lunch_break])

    def test_slot_after_break(self, lunch_break):
        """Slot 14:00, servicio 30min → NO choca (después del break)."""
        slot = {"start": _make_dt(14, 0), "end": _make_dt(14, 30)}
        assert not slot_overlaps_any_break(slot, timedelta(minutes=30), [lunch_break])

    def test_multiple_breaks(self):
        """Dos breaks: 10:30-10:45 y 13:00-14:00."""
        breaks = [
            MockBreak(start_time=time(10, 30), end_time=time(10, 45)),
            MockBreak(start_time=time(13, 0), end_time=time(14, 0))
        ]
        # Slot 10:00, servicio 45min → termina 10:45 → choca con primer break
        slot = {"start": _make_dt(10, 0), "end": _make_dt(10, 45)}
        assert slot_overlaps_any_break(slot, timedelta(minutes=45), breaks)


class TestDayOfWeekConvention:
    """Tests para verificar que se usa ISO 8601 (isoweekday) en todo el sistema."""

    def test_monday_is_1(self):
        """Lunes = 1 (ISO 8601)."""
        monday = date(2026, 4, 20)  # 20 abril 2026 es lunes
        assert monday.isoweekday() == 1

    def test_sunday_is_7(self):
        """Domingo = 7 (ISO 8601)."""
        sunday = date(2026, 4, 26)  # 26 abril 2026 es domingo
        assert sunday.isoweekday() == 7

    def test_weekday_not_used(self):
        """Verificar que weekday() y isoweekday() difieren para domingo."""
        sunday = date(2026, 4, 26)
        assert sunday.weekday() == 6       # weekday: 0=Monday, 6=Sunday
        assert sunday.isoweekday() == 7    # isoweekday: 1=Monday, 7=Sunday
        # ⚠️ Si usáramos weekday(), domingo sería 6, no 7


class TestTimezoneConversion:
    """Tests para verificar conversiones UTC ↔ zona local."""

    def test_lima_to_utc(self):
        """09:00 Lima (UTC-5) → 14:00 UTC."""
        local_dt = datetime(2026, 4, 20, 9, 0, tzinfo=BIZ_TZ)
        utc_dt = local_dt.astimezone(UTC)
        assert utc_dt.hour == 14

    def test_utc_to_lima(self):
        """14:00 UTC → 09:00 Lima."""
        utc_dt = datetime(2026, 4, 20, 14, 0, tzinfo=UTC)
        local_dt = utc_dt.astimezone(BIZ_TZ)
        assert local_dt.hour == 9

    def test_booking_near_midnight_utc(self):
        """Booking a las 23:30 UTC del 19 abril = 18:30 Lima del 19 abril.
        NO debe aparecer en slots del 20 abril."""
        booking_utc = datetime(2026, 4, 19, 23, 30, tzinfo=UTC)
        booking_local = booking_utc.astimezone(BIZ_TZ)
        assert booking_local.date() == date(2026, 4, 19)  # Sigue siendo 19 en Lima
        assert booking_local.hour == 18
        assert booking_local.minute == 30

    def test_day_boundary_search_window(self):
        """Ventana de búsqueda para el 20 abril en Lima:
        00:00 Lima = 05:00 UTC del 20 abril
        23:59 Lima = 04:59 UTC del 21 abril."""
        target = date(2026, 4, 20)
        day_start_local = datetime.combine(target, time(0, 0)).replace(tzinfo=BIZ_TZ)
        day_end_local = datetime.combine(target, time(23, 59, 59)).replace(tzinfo=BIZ_TZ)

        day_start_utc = day_start_local.astimezone(UTC)
        day_end_utc = day_end_local.astimezone(UTC)

        assert day_start_utc.day == 20
        assert day_start_utc.hour == 5
        assert day_end_utc.day == 21
        assert day_end_utc.hour == 4


# Helper para crear datetimes rápido en tests
def _make_dt(hour, minute, tz=BIZ_TZ):
    return datetime(2026, 4, 20, hour, minute, tzinfo=tz)
```

### 16.4 Ejecución de Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Solo motor de slots
pytest tests/test_slot_engine.py -v

# Con cobertura
pytest tests/ --cov=app/services/slot_engine --cov-report=term-missing

# Solo tests de timezone
pytest tests/test_slot_engine.py -k "Timezone" -v
```

### 16.5 Checklist de Cobertura Mínima

| Escenario | Test |
|-----------|------|
| Generación de slots con servicio 30min | ✅ `test_basic_slots_30min_service` |
| Servicio largo reduce slots disponibles | ✅ `test_60min_service_reduces_slots` |
| Servicio más largo que ventana = 0 slots | ✅ `test_empty_when_service_longer_than_window` |
| Break no afecta slot que termina justo antes | ✅ `test_slot_before_break_no_overlap` |
| Servicio largo choca con break por duración | ✅ `test_slot_overlaps_break_due_to_duration` |
| Convención ISO: lunes=1, domingo=7 | ✅ `test_monday_is_1`, `test_sunday_is_7` |
| Conversión Lima→UTC correcta | ✅ `test_lima_to_utc` |
| Booking cerca de medianoche UTC no cruza día | ✅ `test_booking_near_midnight_utc` |
| Ventana de búsqueda respeta timezone | ✅ `test_day_boundary_search_window` |

---

## 17) Plan de Ejecución Recomendado (Integración Real 2026-04-22)

### 17.1 Prioridad P0 (bloqueadores funcionales)

1. **Contrato API único (backend como fuente de verdad)**
   - Resolver desalineaciones activas: `/users`, `/settings/calendar/*`, `/stats/*`.
   - Documentar contrato final y alinear frontend completo.

2. **Flujo de alta de barbero end-to-end**
   - Alta por correo y datos operativos del barbero.
   - Vinculación explícita `barbers.user_id` ↔ `auth.users.id`.
   - Garantizar `profiles.role='barbero'` para permisos correctos.

3. **Visibilidad operativa de inactivos para admin**
   - Mantener exclusión de inactivos para cliente.
   - Exponer gestión admin con `include_inactive=true` para reactivación/auditoría.

### 17.2 Prioridad P1 (operación diaria)

1. Publicar endpoints de dashboard reales y consumirlos en frontend.
2. Cerrar flujos de gestión de reservas para admin y barbero con UX consistente.
3. Ejecutar pruebas E2E de negocio (cliente reserva, barbero gestiona, admin supervisa).

### 17.3 Prioridad P2 (automatización y salida a producción)

1. Fase 3.2: sincronización automática con Google Calendar por eventos de booking.
2. Fase 4: hardening (seguridad, límites, despliegue, observabilidad).

### 17.4 Definición final de estado `barbero.active`

- `active=true`:
  - visible para clientes,
  - elegible para slots,
  - elegible para nuevas reservas.

- `active=false`:
  - no visible para cliente,
  - no genera slots,
  - no permite nuevas reservas,
  - sigue disponible para gestión/admin con filtros de inactivos.

- Reservas históricas se preservan (no borrado físico).
