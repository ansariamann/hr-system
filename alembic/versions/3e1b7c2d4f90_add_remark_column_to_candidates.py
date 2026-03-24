"""Add remark column to candidates

Revision ID: 3e1b7c2d4f90
Revises: f5e2a1b8c3d4
Create Date: 2026-03-23 23:45:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3e1b7c2d4f90"
down_revision = "f5e2a1b8c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS remark TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS remark;
        """
    )
