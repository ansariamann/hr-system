"""enforce_single_hired_application_per_job

Revision ID: ab12cd34ef56
Revises: 8f3c1a2b9d44
Create Date: 2026-04-03 19:20:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "8f3c1a2b9d44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety cleanup for historical data created before this invariant:
    # keep the most recent active HIRED application per job and demote older ones.
    op.execute(
        """
        WITH ranked_hires AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY job_id
                    ORDER BY status_updated_at DESC NULLS LAST, updated_at DESC, created_at DESC, id DESC
                ) AS rn
            FROM applications
            WHERE job_id IS NOT NULL
              AND deleted_at IS NULL
              AND status = 'HIRED'
        )
        UPDATE applications a
        SET
            status = 'WITHDRAWN',
            status_updated_at = NOW(),
            updated_at = NOW(),
            notes = CASE
                WHEN COALESCE(a.notes, '') = '' THEN 'Auto-demoted duplicate HIRED record during invariant migration'
                ELSE a.notes || E'\\nAuto-demoted duplicate HIRED record during invariant migration'
            END
        FROM ranked_hires r
        WHERE a.id = r.id
          AND r.rn > 1;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_applications_one_hired_per_job_active
        ON applications(job_id)
        WHERE job_id IS NOT NULL
          AND deleted_at IS NULL
          AND status = 'HIRED';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_applications_one_hired_per_job_active;")
