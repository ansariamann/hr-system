-- V3: Bootstrap default tenant (client) only.
-- No user accounts are seeded here.
-- Create the first super_admin via the /api/v1/auth/register endpoint after
-- setting BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD env vars,
-- or use the AdminBootstrapService on first startup.

-- 1. Ensure Default Client / Tenant Exists
INSERT INTO clients (id, name, industry, contact_name, contact_email, is_active, created_at, updated_at)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Acme Corp',
    'Enterprise Cloud & SaaS',
    'Administrator',
    'admin@acmecorp.com',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;
