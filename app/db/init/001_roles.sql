-- Owner role for schema/migrations (NOT superuser)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_owner') THEN
    CREATE ROLE app_owner LOGIN PASSWORD 'Rh7224624';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'Rh109724';
  END IF;
END $$;

-- ensure schema ownership
ALTER SCHEMA public OWNER TO app_owner;

-- Ensure app_user cannot bypass RLS
ALTER ROLE app_user SET row_security = on;

-- allow runtime app to use schema
GRANT USAGE ON SCHEMA public TO app_user;

-- Allow connections
GRANT CONNECT ON DATABASE app TO app_owner, app_user;

-- Allow app_owner to create (and drop) databases — needed for isolated test DB lifecycle
ALTER ROLE app_owner CREATEDB;