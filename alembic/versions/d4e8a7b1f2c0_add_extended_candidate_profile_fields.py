"""Add extended candidate profile fields

Revision ID: d4e8a7b1f2c0
Revises: c3a2b6f1d901
Create Date: 2026-02-22 00:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d4e8a7b1f2c0"
down_revision = "c3a2b6f1d901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS present_address TEXT,
        ADD COLUMN IF NOT EXISTS permanent_address TEXT,
        ADD COLUMN IF NOT EXISTS date_of_birth DATE,
        ADD COLUMN IF NOT EXISTS previous_employment JSONB,
        ADD COLUMN IF NOT EXISTS key_skill TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS key_skill,
        DROP COLUMN IF EXISTS previous_employment,
        DROP COLUMN IF EXISTS date_of_birth,
        DROP COLUMN IF EXISTS permanent_address,
        DROP COLUMN IF EXISTS present_address;
        """
    )
