"""Add security audit logs table

Revision ID: 003
Revises: 002
Create Date: 2024-12-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add security audit logs table."""
    # Create enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE securityeventtype AS ENUM ('auth_failure', 'token_replay', 'expired_token', 'rate_limit_exceeded', 'account_locked', 'suspicious_activity', 'rls_bypass_attempt');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE securityeventseverity AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create security audit logs table
    op.create_table(
        'security_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add constraints to ensure enum values
    op.execute("""
        ALTER TABLE security_audit_logs 
        ADD CONSTRAINT check_event_type 
        CHECK (event_type IN ('auth_failure', 'token_replay', 'expired_token', 'rate_limit_exceeded', 'account_locked', 'suspicious_activity', 'rls_bypass_attempt'))
    """)
    
    op.execute("""
        ALTER TABLE security_audit_logs 
        ADD CONSTRAINT check_severity 
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
    """)
    
    # Create indexes for performance
    op.create_index('ix_security_audit_logs_event_type', 'security_audit_logs', ['event_type'])
    op.create_index('ix_security_audit_logs_severity', 'security_audit_logs', ['severity'])
    op.create_index('ix_security_audit_logs_created_at', 'security_audit_logs', ['created_at'])
    op.create_index('ix_security_audit_logs_email', 'security_audit_logs', ['email'])
    op.create_index('ix_security_audit_logs_ip_address', 'security_audit_logs', ['ip_address'])


def downgrade() -> None:
    """Remove security audit logs table."""
    op.drop_index('ix_security_audit_logs_ip_address', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_email', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_created_at', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_severity', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_event_type', table_name='security_audit_logs')
    op.drop_table('security_audit_logs')
    op.execute("DROP TYPE IF EXISTS securityeventseverity")
    op.execute("DROP TYPE IF EXISTS securityeventtype")