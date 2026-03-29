"""add vacant to jobs

Revision ID: 58b6a9d2e4f1
Revises: c4f6a2d9b8e1
Create Date: 2026-03-28 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "58b6a9d2e4f1"
down_revision = "f1c2d3e4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "vacant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(op.f("ix_jobs_vacant"), "jobs", ["vacant"], unique=False)
    op.execute(
        """
        UPDATE jobs
        SET vacant = CASE
            WHEN EXISTS (
                SELECT 1
                FROM applications
                WHERE applications.job_id = jobs.id
                  AND applications.deleted_at IS NULL
                  AND applications.status = 'HIRED'
            ) THEN false
            ELSE true
        END
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_vacant"), table_name="jobs")
    op.drop_column("jobs", "vacant")
