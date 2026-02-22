"""add_jobs_table

Revision ID: 4f1d2b7c9a11
Revises: 2b7b8c3a6f10
Create Date: 2026-02-22 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4f1d2b7c9a11'
down_revision = '2b7b8c3a6f10'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('posting_date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')),
        sa.Column('requirements', sa.Text(), nullable=True),
        sa.Column('experience_required', sa.Integer(), nullable=True),
        sa.Column('salary_lpa', sa.Numeric(10, 2), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    )

    op.create_index('idx_jobs_client_id', 'jobs', ['client_id'])
    op.create_index('idx_jobs_title', 'jobs', ['title'])
    op.create_index('idx_jobs_company_name', 'jobs', ['company_name'])
    op.create_index('idx_jobs_location', 'jobs', ['location'])

    op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY client_isolation_jobs ON jobs
            FOR ALL TO authenticated_users
            USING (client_id = current_setting('app.current_client_id', true)::UUID);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS client_isolation_jobs ON jobs;")
    op.execute("ALTER TABLE jobs DISABLE ROW LEVEL SECURITY;")
    op.drop_index('idx_jobs_location', table_name='jobs')
    op.drop_index('idx_jobs_company_name', table_name='jobs')
    op.drop_index('idx_jobs_title', table_name='jobs')
    op.drop_index('idx_jobs_client_id', table_name='jobs')
    op.drop_table('jobs')
