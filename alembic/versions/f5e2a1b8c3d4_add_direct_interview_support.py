"""Add direct interview support

Revision ID: f5e2a1b8c3d4
Revises: d4e8a7b1f2c0
Create Date: 2026-03-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f5e2a1b8c3d4"
down_revision = "d4e8a7b1f2c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_direct_interview column to candidates table
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS is_direct_interview BOOLEAN DEFAULT FALSE;
        """
    )
    
    # Create interview_records table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES candidates(id),
            client_id UUID NOT NULL REFERENCES clients(id),
            company_id UUID NOT NULL REFERENCES clients(id),
            interviewer_id UUID NOT NULL REFERENCES users(id),
            interview_date TIMESTAMP NOT NULL,
            notes TEXT,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            deleted_at TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_interview_records_candidate_id ON interview_records(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_interview_records_client_id ON interview_records(client_id);
        CREATE INDEX IF NOT EXISTS idx_interview_records_company_id ON interview_records(company_id);
        CREATE INDEX IF NOT EXISTS idx_interview_records_interviewer_id ON interview_records(interviewer_id);
        """
    )


def downgrade() -> None:
    # Drop interview_records table
    op.execute(
        """
        DROP TABLE IF EXISTS interview_records CASCADE;
        """
    )
    
    # Remove is_direct_interview column from candidates table
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS is_direct_interview;
        """
    )
    
    # Remove is_direct_interview column from candidates
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS is_direct_interview;
        """
    )
