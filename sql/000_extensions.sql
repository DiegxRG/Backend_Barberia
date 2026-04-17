-- ============================================================
-- Extensión requerida para EXCLUDE USING gist en bookings
-- EJECUTAR PRIMERO antes de cualquier otra migración
-- ============================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;
