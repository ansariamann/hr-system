"""Make candidate client optional and backfill assignment from applications.

Revision ID: 4a6f0d9c2b31
Revises: ab12cd34ef56
Create Date: 2026-04-06 22:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "4a6f0d9c2b31"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("candidates", "client_id", existing_type=sa.CHAR(length=36), nullable=True)

    op.execute(
        """
        UPDATE candidates
        SET client_id = NULL
        WHERE id NOT IN (
            SELECT DISTINCT candidate_id
            FROM applications
            WHERE candidate_id IS NOT NULL
        )
        """
    )

    op.execute(
        """
        UPDATE candidates AS c
        SET client_id = latest_app.client_id
        FROM (
            SELECT DISTINCT ON (a.candidate_id)
                a.candidate_id,
                a.client_id
            FROM applications AS a
            WHERE a.candidate_id IS NOT NULL
            ORDER BY a.candidate_id,
                     CASE WHEN a.deleted_at IS NULL THEN 0 ELSE 1 END,
                     COALESCE(a.application_date, a.created_at) DESC,
                     a.created_at DESC
        ) AS latest_app
        WHERE c.id = latest_app.candidate_id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM candidates
        WHERE client_id IS NULL
        """
    )
    op.alter_column("candidates", "client_id", existing_type=sa.CHAR(length=36), nullable=False)
