"""add selected client name to candidates

Revision ID: f1c2d3e4b5a6
Revises: e6f7a8b9c0d1
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "f1c2d3e4b5a6"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("selected_client_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidates", "selected_client_name")
