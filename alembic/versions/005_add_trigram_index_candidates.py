"""Add trigram index for candidate fuzzy matching

Revision ID: 005
Revises: 004
Create Date: 2025-12-25 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add trigram index for candidate fuzzy matching."""

    # Enable pg_trgm extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Create GIN index on name using trigram ops
    # This allows ILIKE '%name%' to use the index
    op.create_index(
        'idx_candidates_name_trgm',
        'candidates',
        ['name'],
        postgresql_using='gin',
        postgresql_ops={'name': 'gin_trgm_ops'}
    )


def downgrade() -> None:
    """Remove trigram index."""

    # Drop index
    op.drop_index('idx_candidates_name_trgm', table_name='candidates')

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
