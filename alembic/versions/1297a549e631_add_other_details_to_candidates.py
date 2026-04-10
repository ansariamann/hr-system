"""add_other_details_to_candidates

Revision ID: 1297a549e631
Revises: 4a6f0d9c2b31
Create Date: 2026-04-10 22:03:41.296101

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1297a549e631'
down_revision = '4a6f0d9c2b31'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('other_details', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'other_details')
