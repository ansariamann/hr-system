"""Add resume_file_path column to candidates

Revision ID: 9f2a1c4b7e11
Revises: 6b9f6c5d2a10
Create Date: 2026-02-21 00:00:01.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9f2a1c4b7e11"
down_revision = "6b9f6c5d2a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS resume_file_path TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS resume_file_path;
        """
    )
