"""add extended fields to clients

Revision ID: a1b2c3d4e5f6
Revises: 7c2e3f8146a1
Create Date: 2026-03-25 14:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "7c2e3f8146a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("industry", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("clients", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("clients", sa.Column("contact_phone", sa.String(length=50), nullable=True))
    op.add_column("clients", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("clients", sa.Column("website", sa.String(length=500), nullable=True))
    op.add_column(
        "clients",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("clients", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("clients", "is_active")
    op.drop_column("clients", "website")
    op.drop_column("clients", "address")
    op.drop_column("clients", "contact_phone")
    op.drop_column("clients", "contact_email")
    op.drop_column("clients", "contact_name")
    op.drop_column("clients", "industry")
