-- ============================================================
-- Hardening de roles de perfil
-- Objetivo:
-- 1) Todo registro nuevo inicia como 'cliente' (sin confiar en metadata.role)
-- 2) Usuarios no pueden autoescalar rol en updates directos vía ANON_KEY
-- ============================================================

-- 1) Trigger de alta: rol fijo a cliente
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
    'cliente'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2) RLS: actualización de perfil propio sin cambiar rol
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (
    auth.uid() = id
    AND role = (SELECT p.role FROM profiles p WHERE p.id = auth.uid())
  );
