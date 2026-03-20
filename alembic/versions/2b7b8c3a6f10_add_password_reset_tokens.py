"""add_password_reset_tokens

Revision ID: 2b7b8c3a6f10
Revises: edf1ed5dfbab
Create Date: 2026-02-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2b7b8c3a6f10'
down_revision = 'edf1ed5dfbab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration may be encountered on environments where the table was created
    # outside Alembic (or via a different branch). Make it idempotent so upgrades
    # can converge cleanly.
    conn = op.get_bind()
    exists = conn.execute(sa.text("SELECT to_regclass('public.password_reset_tokens')")).scalar()

    if not exists:
        op.create_table(
            'password_reset_tokens',
            sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('token_hash', sa.String(length=128), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('requested_ip', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        )

    # Ensure indexes exist (Postgres supports IF NOT EXISTS for indexes).
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id "
        "ON password_reset_tokens (user_id);"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash "
        "ON password_reset_tokens (token_hash);"
    )

    # Enable RLS and (re)create policy for client isolation.
    op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS client_isolation_password_reset_tokens ON password_reset_tokens;")
    op.execute(
        """
        CREATE POLICY client_isolation_password_reset_tokens ON password_reset_tokens
            FOR ALL TO authenticated_users
            USING (
                user_id IN (
                    SELECT id FROM users
                    WHERE client_id = current_setting('app.current_client_id', true)::UUID
                )
            );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS client_isolation_password_reset_tokens ON password_reset_tokens;")
    op.execute("ALTER TABLE password_reset_tokens DISABLE ROW LEVEL SECURITY;")
    op.drop_index('idx_password_reset_tokens_token_hash', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_tokens_user_id', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
