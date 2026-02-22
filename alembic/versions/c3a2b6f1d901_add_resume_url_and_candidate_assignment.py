"""Add resume_url and assigned_user_id to candidates

Revision ID: c3a2b6f1d901
Revises: 9f2a1c4b7e11
Create Date: 2026-02-21 23:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c3a2b6f1d901"
down_revision = "9f2a1c4b7e11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS resume_url TEXT;
        """
    )

    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS assigned_user_id UUID;
        """
    )

    op.execute(
        """
        UPDATE candidates
        SET resume_url = resume_file_path
        WHERE resume_url IS NULL AND resume_file_path IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_candidates_assigned_user_id
        ON candidates (assigned_user_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_candidates_assigned_user_id;")

    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS assigned_user_id;
        """
    )

    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS resume_url;
        """
    )
