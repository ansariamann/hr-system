"""Add position and skills to interview records.

Revision ID: 6b0b8eb8bb91
Revises: 81c9f1588e55
Create Date: 2026-03-23 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6b0b8eb8bb91"
down_revision = "81c9f1588e55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_records", sa.Column("position", sa.String(length=255), nullable=True))
    op.add_column("interview_records", sa.Column("skills", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_records", "skills")
    op.drop_column("interview_records", "position")
