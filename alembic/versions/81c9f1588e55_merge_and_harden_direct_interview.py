"""merge_and_harden_direct_interview

Revision ID: 81c9f1588e55
Revises: 9d7ba6c7c576, f5e2a1b8c3d4
Create Date: 2026-03-22 23:36:10.672947

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '81c9f1588e55'
down_revision = ('9d7ba6c7c576', 'f5e2a1b8c3d4')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_records
        ADD CONSTRAINT interview_records_rating_range_chk
        CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_interview_records_created_at
        ON interview_records(created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_interview_records_deleted_at
        ON interview_records(deleted_at);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_interview_records_candidate_company_date_active
        ON interview_records(candidate_id, company_id, interview_date)
        WHERE deleted_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_interview_records_candidate_company_date_active;")
    op.execute("DROP INDEX IF EXISTS idx_interview_records_deleted_at;")
    op.execute("DROP INDEX IF EXISTS idx_interview_records_created_at;")
    op.execute("ALTER TABLE interview_records DROP CONSTRAINT IF EXISTS interview_records_rating_range_chk;")
