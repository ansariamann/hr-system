"""add core recruitment fields

Revision ID: e6f7a8b9c0d1
Revises: c4f6a2d9b8e1, 6b0b8eb8bb91
Create Date: 2026-03-26 22:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = ("c4f6a2d9b8e1", "6b0b8eb8bb91")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("total_experience_years", sa.Numeric(5, 2), nullable=True))
    op.add_column("candidates", sa.Column("notice_period_days", sa.Integer(), nullable=True))
    op.add_column(
        "candidates",
        sa.Column("source", sa.String(length=100), nullable=False, server_default="MANUAL"),
    )
    op.add_column("candidates", sa.Column("linkedin_url", sa.String(length=500), nullable=True))
    op.create_index("ix_candidates_source", "candidates", ["source"], unique=False)

    op.add_column("jobs", sa.Column("closing_date", sa.Date(), nullable=True))
    op.add_column("jobs", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("employment_type", sa.String(length=50), nullable=False, server_default="FULL_TIME"),
    )
    op.add_column(
        "jobs",
        sa.Column("openings_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "jobs",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="OPEN"),
    )
    op.create_index("ix_jobs_department", "jobs", ["department"], unique=False)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)

    op.add_column("applications", sa.Column("job_id", sa.UUID(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("source", sa.String(length=100), nullable=False, server_default="MANUAL"),
    )
    op.add_column("applications", sa.Column("status_updated_at", sa.DateTime(), nullable=True))
    op.add_column("applications", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("applied_by_user_id", sa.UUID(), nullable=True))

    op.execute(
        """
        UPDATE applications
        SET status_updated_at = COALESCE(updated_at, application_date, created_at, NOW())
        WHERE status_updated_at IS NULL;
        """
    )

    op.alter_column("applications", "status_updated_at", nullable=False)
    op.create_index("ix_applications_job_id", "applications", ["job_id"], unique=False)
    op.create_index("ix_applications_source", "applications", ["source"], unique=False)
    op.create_index("ix_applications_applied_by_user_id", "applications", ["applied_by_user_id"], unique=False)
    op.create_foreign_key(
        "fk_applications_job_id_jobs",
        "applications",
        "jobs",
        ["job_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_applications_applied_by_user_id_users",
        "applications",
        "users",
        ["applied_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_applications_applied_by_user_id_users", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_job_id_jobs", "applications", type_="foreignkey")
    op.drop_index("ix_applications_applied_by_user_id", table_name="applications")
    op.drop_index("ix_applications_source", table_name="applications")
    op.drop_index("ix_applications_job_id", table_name="applications")
    op.drop_column("applications", "applied_by_user_id")
    op.drop_column("applications", "notes")
    op.drop_column("applications", "status_updated_at")
    op.drop_column("applications", "source")
    op.drop_column("applications", "job_id")

    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_department", table_name="jobs")
    op.drop_column("jobs", "status")
    op.drop_column("jobs", "openings_count")
    op.drop_column("jobs", "employment_type")
    op.drop_column("jobs", "department")
    op.drop_column("jobs", "closing_date")

    op.drop_index("ix_candidates_source", table_name="candidates")
    op.drop_column("candidates", "linkedin_url")
    op.drop_column("candidates", "source")
    op.drop_column("candidates", "notice_period_days")
    op.drop_column("candidates", "total_experience_years")
