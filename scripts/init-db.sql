-- Database initialization script for ATS Backend
-- This script sets up the database with proper extensions and initial configuration

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text matching

-- Create authenticated_users role for RLS policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated_users') THEN
        CREATE ROLE authenticated_users;
    END IF;
END
$$;

-- Grant necessary permissions to the application user
GRANT authenticated_users TO ats_user;

-- Create a function to generate candidate hash for duplicate detection
CREATE OR REPLACE FUNCTION generate_candidate_hash(
    p_name TEXT,
    p_email TEXT DEFAULT NULL,
    p_phone TEXT DEFAULT NULL
) RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN encode(
        digest(
            LOWER(TRIM(COALESCE(p_name, ''))) || '|' ||
            LOWER(TRIM(COALESCE(p_email, ''))) || '|' ||
            REGEXP_REPLACE(COALESCE(p_phone, ''), '[^0-9]', '', 'g'),
            'sha256'
        ),
        'hex'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create a function to set updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a function to validate client context for RLS
CREATE OR REPLACE FUNCTION validate_client_context()
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if current_setting exists and is a valid UUID
    BEGIN
        PERFORM current_setting('app.current_client_id', true)::UUID;
        RETURN true;
    EXCEPTION WHEN OTHERS THEN
        RETURN false;
    END;
END;
$$ LANGUAGE plpgsql;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'ATS Database initialization completed successfully';
    RAISE NOTICE 'Extensions enabled: uuid-ossp, pg_trgm';
    RAISE NOTICE 'Functions created: generate_candidate_hash, update_updated_at_column, validate_client_context';
    RAISE NOTICE 'Role created: authenticated_users';
END
$$;