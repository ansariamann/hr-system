# ATS Backend Database Schema

This document describes the database schema implementation for the ATS Backend System, including multi-tenant Row-Level Security (RLS) policies.

## Overview

The database schema implements a multi-tenant architecture using PostgreSQL Row-Level Security (RLS) to ensure strict data isolation between client organizations. The schema includes four main entities: Clients, Candidates, Applications, and Resume Jobs.

## Database Tables

### Clients Table

Stores tenant organization information.

```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email_domain VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Candidates Table

Stores job applicant information with JSONB fields for flexible data storage.

```sql
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    skills JSONB,
    experience JSONB,
    ctc_current DECIMAL(12,2),
    ctc_expected DECIMAL(12,2),
    status VARCHAR(50) DEFAULT 'ACTIVE' NOT NULL,
    candidate_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Applications Table

Links candidates to specific job applications with soft delete support.

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    candidate_id UUID NOT NULL REFERENCES candidates(id),
    job_title VARCHAR(255),
    application_date TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'RECEIVED' NOT NULL,
    flagged_for_review BOOLEAN DEFAULT FALSE NOT NULL,
    flag_reason TEXT,
    deleted_at TIMESTAMP,  -- Soft delete
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Resume Jobs Table

Tracks resume processing tasks with email deduplication.

```sql
CREATE TABLE resume_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    email_message_id VARCHAR(255) UNIQUE,  -- For deduplication
    file_name VARCHAR(255),
    file_path TEXT,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    error_message TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Row-Level Security (RLS) Policies

RLS policies ensure that each client can only access their own data:

```sql
-- Enable RLS on all tenant tables
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_jobs ENABLE ROW LEVEL SECURITY;

-- Create isolation policies
CREATE POLICY client_isolation_candidates ON candidates
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_client_id', true)::UUID);

CREATE POLICY client_isolation_applications ON applications
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_client_id', true)::UUID);

CREATE POLICY client_isolation_resume_jobs ON resume_jobs
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_client_id', true)::UUID);
```

## Database Functions

### Candidate Hash Generation

Automatically generates hash values for duplicate detection:

```sql
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
```

### Updated At Trigger

Automatically updates timestamp fields:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## Triggers

### Automatic Hash Generation

```sql
CREATE TRIGGER update_candidate_hash_trigger
    BEFORE INSERT OR UPDATE ON candidates
    FOR EACH ROW
    EXECUTE FUNCTION update_candidate_hash();
```

### Timestamp Updates

```sql
CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

## Indexes

Performance optimization indexes:

```sql
-- Candidates
CREATE INDEX idx_candidates_client_id ON candidates(client_id);
CREATE INDEX idx_candidates_hash ON candidates(candidate_hash);
CREATE INDEX idx_candidates_email ON candidates(email);

-- Applications
CREATE INDEX idx_applications_client_id ON applications(client_id);
CREATE INDEX idx_applications_candidate_id ON applications(candidate_id);
CREATE INDEX idx_applications_deleted_at ON applications(deleted_at);

-- Resume Jobs
CREATE INDEX idx_resume_jobs_client_id ON resume_jobs(client_id);
CREATE INDEX idx_resume_jobs_status ON resume_jobs(status);
```

## Session Context Management

The system uses session context to enforce RLS policies:

```python
from ats_backend.core.session_context import set_client_context

# Set client context for RLS
with db_session() as session:
    set_client_context(session, client_id)
    # All queries now automatically filtered by client_id
    candidates = session.query(Candidate).all()
```

## Migration Management

Database migrations are managed using Alembic:

```bash
# Run migrations
python scripts/setup_database.py

# Create new migration
alembic revision --autogenerate -m "Description"

# Upgrade to latest
alembic upgrade head
```

## Data Integrity Features

1. **Foreign Key Constraints**: Ensure referential integrity
2. **Unique Constraints**: Prevent duplicate email message IDs
3. **Check Constraints**: Validate data formats
4. **Soft Deletes**: Preserve historical data for applications
5. **Automatic Timestamps**: Track creation and modification times
6. **Hash Generation**: Enable efficient duplicate detection

## Security Features

1. **Row-Level Security**: Automatic client data isolation
2. **Session Context**: Secure client identification
3. **Role-Based Access**: authenticated_users role for RLS
4. **Input Validation**: Prevent SQL injection through ORM
5. **Audit Trail**: Track all data modifications

## Requirements Satisfied

- ✅ **3.1**: Client session context for RLS
- ✅ **3.2**: Automatic data filtering by client
- ✅ **3.3**: Cross-client data access prevention
- ✅ **3.4**: Automatic client association for new records
- ✅ **5.3**: Database migration automation

## Usage Examples

### Creating a Client

```python
client = Client(name="Acme Corp", email_domain="acme.com")
session.add(client)
session.commit()
```

### Adding a Candidate with Context

```python
with db_session() as session:
    set_client_context(session, client.id)

    candidate = Candidate(
        name="John Doe",
        email="john@example.com",
        skills={"languages": ["Python", "JavaScript"]},
        ctc_current=Decimal("50000.00")
    )
    session.add(candidate)
    session.commit()
    # candidate.client_id automatically set to client.id
```

### Soft Deleting an Application

```python
application.soft_delete()
session.commit()
# application.deleted_at now set, record preserved
```
