"""add_company_to_candidates

Revision ID: c2afd1b1a965
Revises: 1f55e0428a9d
Create Date: 2026-03-19 14:31:11.204259

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2afd1b1a965'
down_revision = '1f55e0428a9d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS company VARCHAR(255);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidates
        DROP COLUMN IF EXISTS company;
        """
    )
