"""backfill_candidate_company

Revision ID: 9d7ba6c7c576
Revises: c2afd1b1a965
Create Date: 2026-03-19 14:43:38.253386

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9d7ba6c7c576'
down_revision = 'c2afd1b1a965'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill company for existing candidates using previous_employment JSON/JSONB.
    # We take the first entry's company-like field as a pragmatic approximation.
    op.execute(
        """
        UPDATE candidates
        SET company = COALESCE(
            NULLIF(BTRIM((previous_employment::jsonb->0->>'company')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->0->>'company_name')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->0->>'employer')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->0->>'organization')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->0->>'org')), '')
        )
        WHERE (company IS NULL OR company = '')
          AND previous_employment IS NOT NULL
          AND jsonb_typeof(previous_employment::jsonb) = 'array'
          AND jsonb_array_length(previous_employment::jsonb) > 0;
        """
    )

    # Handle rare cases where previous_employment is an object.
    op.execute(
        """
        UPDATE candidates
        SET company = COALESCE(
            NULLIF(BTRIM((previous_employment::jsonb->>'company')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->>'company_name')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->>'employer')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->>'organization')), ''),
            NULLIF(BTRIM((previous_employment::jsonb->>'org')), '')
        )
        WHERE (company IS NULL OR company = '')
          AND previous_employment IS NOT NULL
          AND jsonb_typeof(previous_employment::jsonb) = 'object';
        """
    )


def downgrade() -> None:
    # Non-destructive: keep any populated values.
    return
