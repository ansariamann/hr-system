"""add submitted_by_client to jobs

Revision ID: c4f6a2d9b8e1
Revises: b7c8d9e0f1a2
Create Date: 2026-03-25 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4f6a2d9b8e1"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "submitted_by_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "submitted_by_client")
