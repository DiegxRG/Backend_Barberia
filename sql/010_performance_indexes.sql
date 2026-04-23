-- ============================================================
-- Performance indexes (fase de optimizacion)
-- Objetivo: acelerar filtros y listados frecuentes
-- ============================================================

-- Profiles (listados admin con filtros por rol/activo y orden por nombre)
CREATE INDEX IF NOT EXISTS idx_profiles_active_name
  ON profiles(active, full_name);

CREATE INDEX IF NOT EXISTS idx_profiles_role_active_name
  ON profiles(role, active, full_name);

-- Barbers (catalogo y vinculacion user_id)
CREATE INDEX IF NOT EXISTS idx_barbers_active_name
  ON barbers(active, full_name);

CREATE INDEX IF NOT EXISTS idx_barbers_user_id
  ON barbers(user_id);

-- Services (catalogo por activo/categoria/nombre)
CREATE INDEX IF NOT EXISTS idx_services_active_category_name
  ON services(active, category, name);

-- Availability / breaks (lookup de slots)
CREATE INDEX IF NOT EXISTS idx_availability_rules_active_lookup
  ON availability_rules(barber_id, day_of_week)
  WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_breaks_lookup
  ON breaks(barber_id, day_of_week, active, start_time);

-- Bookings (listados operativos por estado y agenda)
CREATE INDEX IF NOT EXISTS idx_bookings_status_start
  ON bookings(status, start_at);

CREATE INDEX IF NOT EXISTS idx_bookings_barber_status_start
  ON bookings(barber_id, status, start_at);
