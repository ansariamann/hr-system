"""Initial schema with RLS policies

Revision ID: 001
Revises: 
Create Date: 2025-12-22 23:06:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema with RLS policies."""
    
    # Create clients table
    op.execute("""
        CREATE TABLE clients (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            email_domain VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create candidates table
    op.execute("""
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
    """)
    
    # Create applications table
    op.execute("""
        CREATE TABLE applications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID NOT NULL REFERENCES clients(id),
            candidate_id UUID NOT NULL REFERENCES candidates(id),
            job_title VARCHAR(255),
            application_date TIMESTAMP DEFAULT NOW(),
            status VARCHAR(50) DEFAULT 'RECEIVED' NOT NULL,
            flagged_for_review BOOLEAN DEFAULT FALSE NOT NULL,
            flag_reason TEXT,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create resume_jobs table
    op.execute("""
        CREATE TABLE resume_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID NOT NULL REFERENCES clients(id),
            email_message_id VARCHAR(255) UNIQUE,
            file_name VARCHAR(255),
            file_path TEXT,
            status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
            error_message TEXT,
            processed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create indexes for performance
    op.create_index('idx_candidates_client_id', 'candidates', ['client_id'])
    op.create_index('idx_candidates_hash', 'candidates', ['candidate_hash'])
    op.create_index('idx_candidates_email', 'candidates', ['email'])
    op.create_index('idx_applications_client_id', 'applications', ['client_id'])
    op.create_index('idx_applications_candidate_id', 'applications', ['candidate_id'])
    op.create_index('idx_applications_deleted_at', 'applications', ['deleted_at'])
    op.create_index('idx_resume_jobs_client_id', 'resume_jobs', ['client_id'])
    op.create_index('idx_resume_jobs_status', 'resume_jobs', ['status'])
    
    # Create triggers for updated_at columns
    op.execute("""
        CREATE TRIGGER update_clients_updated_at
            BEFORE UPDATE ON clients
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_candidates_updated_at
            BEFORE UPDATE ON candidates
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_applications_updated_at
            BEFORE UPDATE ON applications
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Create trigger for candidate hash generation
    op.execute("""
        CREATE OR REPLACE FUNCTION update_candidate_hash()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.candidate_hash = generate_candidate_hash(NEW.name, NEW.email, NEW.phone);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER update_candidate_hash_trigger
            BEFORE INSERT OR UPDATE ON candidates
            FOR EACH ROW
            EXECUTE FUNCTION update_candidate_hash();
    """)
    
    # Enable Row Level Security on all tenant tables
    op.execute("ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE applications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE resume_jobs ENABLE ROW LEVEL SECURITY;")
    
    # Create RLS policies for client isolation
    op.execute("""
        CREATE POLICY client_isolation_candidates ON candidates
            FOR ALL TO authenticated_users
            USING (client_id = current_setting('app.current_client_id', true)::UUID);
    """)
    
    op.execute("""
        CREATE POLICY client_isolation_applications ON applications
            FOR ALL TO authenticated_users
            USING (client_id = current_setting('app.current_client_id', true)::UUID);
    """)
    
    op.execute("""
        CREATE POLICY client_isolation_resume_jobs ON resume_jobs
            FOR ALL TO authenticated_users
            USING (client_id = current_setting('app.current_client_id', true)::UUID);
    """)


def downgrade() -> None:
    """Drop all tables and policies."""
    
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS client_isolation_candidates ON candidates;")
    op.execute("DROP POLICY IF EXISTS client_isolation_applications ON applications;")
    op.execute("DROP POLICY IF EXISTS client_isolation_resume_jobs ON resume_jobs;")
    
    # Disable RLS
    op.execute("ALTER TABLE candidates DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE applications DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE resume_jobs DISABLE ROW LEVEL SECURITY;")
    
    # Drop triggers and functions
    op.execute("DROP TRIGGER IF EXISTS update_candidate_hash_trigger ON candidates;")
    op.execute("DROP FUNCTION IF EXISTS update_candidate_hash();")
    op.execute("DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;")
    op.execute("DROP TRIGGER IF EXISTS update_candidates_updated_at ON candidates;")
    op.execute("DROP TRIGGER IF EXISTS update_clients_updated_at ON clients;")
    
    # Drop indexes
    op.drop_index('idx_resume_jobs_status')
    op.drop_index('idx_resume_jobs_client_id')
    op.drop_index('idx_applications_deleted_at')
    op.drop_index('idx_applications_candidate_id')
    op.drop_index('idx_applications_client_id')
    op.drop_index('idx_candidates_email')
    op.drop_index('idx_candidates_hash')
    op.drop_index('idx_candidates_client_id')
    
    # Drop tables
    op.execute("DROP TABLE IF EXISTS resume_jobs;")
    op.execute("DROP TABLE IF EXISTS applications;")
    op.execute("DROP TABLE IF EXISTS candidates;")
    op.execute("DROP TABLE IF EXISTS clients;")