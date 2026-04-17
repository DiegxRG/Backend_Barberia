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
