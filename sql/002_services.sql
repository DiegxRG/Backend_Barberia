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
