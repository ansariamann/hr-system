"""Add company_employees table.

Revision ID: 6bfd8de3219c
Revises: 58b6a9d2e4f1
Create Date: 2026-03-28 23:47:55.474763
"""

from alembic import op
import sqlalchemy as sa

from ats_backend.core.custom_types import GUID


# revision identifiers, used by Alembic.
revision = "6bfd8de3219c"
down_revision = "58b6a9d2e4f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_employees",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("candidate_id", GUID(), nullable=True),
        sa.Column("application_id", GUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("date_of_joining", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_employees_candidate_id"),
        "company_employees",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_employees_client_id"),
        "company_employees",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_company_employees_client_id"), table_name="company_employees")
    op.drop_index(op.f("ix_company_employees_candidate_id"), table_name="company_employees")
    op.drop_table("company_employees")
