"""Add location column to candidates table

Revision ID: 6b9f6c5d2a10
Revises: edf1ed5dfbab
Create Date: 2026-02-21 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6b9f6c5d2a10"
down_revision = "edf1ed5dfbab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add location column to candidates table if missing."""
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS location VARCHAR(255);
        """
    )


def downgrade() -> None:
    """Remove location column from candidates table if present."""
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS location;
        """
    )
