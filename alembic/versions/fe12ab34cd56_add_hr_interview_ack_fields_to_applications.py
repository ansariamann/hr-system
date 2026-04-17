"""add hr interview acknowledgement fields to applications

Revision ID: fe12ab34cd56
Revises: bc83c218d6b5
Create Date: 2026-04-14 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

from ats_backend.core.custom_types import GUID


# revision identifiers, used by Alembic.
revision = "fe12ab34cd56"
down_revision = "bc83c218d6b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "hr_interview_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "applications",
        sa.Column("hr_interview_acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("hr_interview_acknowledged_by", GUID(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("hr_interview_ack_note", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_applications_hr_interview_acknowledged_by_users",
        "applications",
        "users",
        ["hr_interview_acknowledged_by"],
        ["id"],
    )
    op.add_column(
        "interview_records",
        sa.Column("job_id", GUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_records_job_id_jobs",
        "interview_records",
        "jobs",
        ["job_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_interview_records_job_id_jobs",
        "interview_records",
        type_="foreignkey",
    )
    op.drop_column("interview_records", "job_id")
    op.drop_constraint(
        "fk_applications_hr_interview_acknowledged_by_users",
        "applications",
        type_="foreignkey",
    )
    op.drop_column("applications", "hr_interview_ack_note")
    op.drop_column("applications", "hr_interview_acknowledged_by")
    op.drop_column("applications", "hr_interview_acknowledged_at")
    op.drop_column("applications", "hr_interview_acknowledged")
