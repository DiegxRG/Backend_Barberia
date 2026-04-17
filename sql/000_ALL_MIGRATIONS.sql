-- ===== sql\000_extensions.sql =====
-- ============================================================
-- Extensión requerida para EXCLUDE USING gist en bookings
-- EJECUTAR PRIMERO antes de cualquier otra migración
-- ============================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;


-- ===== sql\001_profiles.sql =====
-- ============================================================
-- Tabla: profiles
-- Extiende auth.users de Supabase con datos adicionales
-- ============================================================

CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL,
  phone TEXT,
  avatar_url TEXT,
  role TEXT NOT NULL DEFAULT 'cliente' CHECK (role IN ('admin', 'barbero', 'cliente')),
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger para crear perfil automáticamente al registrar usuario
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
    COALESCE(NEW.raw_user_meta_data->>'role', 'cliente')
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ===== sql\002_services.sql =====
-- ============================================================
-- Tabla: services
-- Catálogo de servicios de la barbería
-- ============================================================

CREATE TABLE services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
  price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
  category TEXT DEFAULT 'general' CHECK (category IN ('corte', 'barba', 'combo', 'tratamiento', 'especial', 'general')),
  image_url TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER services_updated_at
  BEFORE UPDATE ON services
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Datos iniciales de ejemplo
INSERT INTO services (name, description, duration_minutes, price, category) VALUES
  ('Corte Clásico', 'Corte de cabello tradicional con tijera y máquina', 30, 25.00, 'corte'),
  ('Corte + Barba', 'Corte de cabello completo más arreglo de barba', 45, 40.00, 'combo'),
  ('Arreglo de Barba', 'Perfilado y arreglo de barba con navaja', 20, 15.00, 'barba'),
  ('Corte Degradado', 'Fade/degradado con diseño personalizado', 40, 35.00, 'corte'),
  ('Tratamiento Capilar', 'Hidratación y tratamiento para el cabello', 60, 50.00, 'tratamiento');


-- ===== sql\003_barbers.sql =====
-- ============================================================
-- Tablas: barbers + barber_services
-- Barberos del negocio y sus servicios asignados
-- ============================================================

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

CREATE TRIGGER barbers_updated_at
  BEFORE UPDATE ON barbers
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Relación N:N barbero ↔ servicio
CREATE TABLE barber_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  UNIQUE(barber_id, service_id)
);


-- ===== sql\004_availability.sql =====
-- ============================================================
-- Tablas: availability_rules + breaks + day_off
-- Sistema de disponibilidad de barberos
--
-- CONVENCIÓN day_of_week: ISO 8601
-- 1=Lunes, 2=Martes, 3=Miércoles, 4=Jueves,
-- 5=Viernes, 6=Sábado, 7=Domingo
--
-- Python: date.isoweekday()
-- PostgreSQL: EXTRACT(ISODOW FROM date)
-- ============================================================

-- Horario base semanal por barbero
CREATE TABLE availability_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  -- ISO 8601: 1=Lunes, 2=Martes, ..., 7=Domingo
  day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  slot_interval_minutes INTEGER DEFAULT 30,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_time_range CHECK (start_time < end_time),
  UNIQUE(barber_id, day_of_week)
);

-- Pausas/almuerzos por día de semana
CREATE TABLE breaks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  -- ISO 8601: 1=Lunes ... 7=Domingo
  day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  description TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_break_range CHECK (start_time < end_time)
);

-- Días libres / vacaciones
CREATE TABLE day_off (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  barber_id UUID NOT NULL REFERENCES barbers(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(barber_id, date)
);


-- ===== sql\005_bookings.sql =====
-- ============================================================
-- Tablas: bookings + booking_history
-- Sistema de reservas con prevención de doble booking
-- ============================================================

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
  calendar_event_id TEXT,  -- ID del evento en Google Calendar (si está sincronizado)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Evitar doble reserva: no pueden solaparse citas del mismo barbero
  -- Solo aplica a bookings que NO están cancelados
  EXCLUDE USING gist (
    barber_id WITH =,
    tstzrange(start_at, end_at) WITH &&
  ) WHERE (status NOT IN ('cancelled'))
);

-- Índices para performance
CREATE INDEX idx_bookings_barber_date ON bookings(barber_id, start_at);
CREATE INDEX idx_bookings_client ON bookings(client_user_id, start_at);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_idempotency ON bookings(idempotency_key);

CREATE TRIGGER bookings_updated_at
  BEFORE UPDATE ON bookings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Historial de cambios de estado
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

CREATE INDEX idx_booking_history_booking ON booking_history(booking_id);


-- ===== sql\006_calendar_tokens.sql =====
-- ============================================================
-- Tabla: google_calendar_tokens
-- Almacena tokens OAuth de Google Calendar por usuario
-- Los tokens se guardan cifrados con Fernet (cryptography)
-- ============================================================

CREATE TABLE google_calendar_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL,       -- Cifrado con Fernet
  refresh_token TEXT NOT NULL,      -- Cifrado con Fernet
  token_expires_at TIMESTAMPTZ NOT NULL,
  calendar_id TEXT DEFAULT 'primary',
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id)
);

CREATE TRIGGER calendar_tokens_updated_at
  BEFORE UPDATE ON google_calendar_tokens
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ===== sql\007_rls_policies.sql =====
-- ============================================================
-- Row Level Security (RLS) Policies
--
-- NOTA: El backend usa SERVICE_ROLE_KEY que bypasea RLS.
-- Estas políticas son una capa de seguridad ADICIONAL
-- para proteger datos si alguien accede directamente a Supabase
-- desde el frontend con la ANON_KEY.
-- ============================================================

-- ── Profiles ────────────────────────────────────────────────
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Usuarios pueden ver su propio perfil
CREATE POLICY "Users can view own profile"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

-- Usuarios pueden actualizar su propio perfil
CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE
  USING (auth.uid() = id);

-- ── Services ────────────────────────────────────────────────
ALTER TABLE services ENABLE ROW LEVEL SECURITY;

-- Todos pueden ver servicios activos (catálogo público)
CREATE POLICY "Anyone can view active services"
  ON services FOR SELECT
  USING (active = TRUE);

-- ── Barbers ─────────────────────────────────────────────────
ALTER TABLE barbers ENABLE ROW LEVEL SECURITY;

-- Todos pueden ver barberos activos
CREATE POLICY "Anyone can view active barbers"
  ON barbers FOR SELECT
  USING (active = TRUE);

-- ── Bookings ────────────────────────────────────────────────
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

-- Clientes pueden ver sus propias reservas
CREATE POLICY "Clients can view own bookings"
  ON bookings FOR SELECT
  USING (auth.uid() = client_user_id);

-- Clientes pueden crear reservas
CREATE POLICY "Clients can create bookings"
  ON bookings FOR INSERT
  WITH CHECK (auth.uid() = client_user_id);


