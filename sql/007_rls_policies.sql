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
