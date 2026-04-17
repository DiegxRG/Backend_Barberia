-- ============================================================
-- Evita solapamiento de breaks por barbero y día (ISO DOW)
-- ============================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'breaks_no_overlap'
  ) THEN
    ALTER TABLE breaks
      ADD CONSTRAINT breaks_no_overlap
      EXCLUDE USING gist (
        barber_id WITH =,
        day_of_week WITH =,
        int4range(
          EXTRACT(EPOCH FROM start_time)::integer,
          EXTRACT(EPOCH FROM end_time)::integer,
          '[)'
        ) WITH &&
      );
  END IF;
END
$$;
