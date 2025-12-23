"""Add users table for authentication

Revision ID: 002
Revises: 001
Create Date: 2025-12-22 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add users table for authentication."""
    
    # Create users table
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            client_id UUID NOT NULL REFERENCES clients(id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create indexes for performance
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_client_id', 'users', ['client_id'])
    op.create_index('idx_users_active', 'users', ['is_active'])
    
    # Create trigger for updated_at column
    op.execute("""
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Enable Row Level Security on users table
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")
    
    # Create RLS policy for users - users can only see users from their own client
    op.execute("""
        CREATE POLICY client_isolation_users ON users
            FOR ALL TO authenticated_users
            USING (client_id = current_setting('app.current_client_id', true)::UUID);
    """)


def downgrade() -> None:
    """Drop users table."""
    
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS client_isolation_users ON users;")
    
    # Disable RLS
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")
    
    # Drop indexes
    op.drop_index('idx_users_active')
    op.drop_index('idx_users_client_id')
    op.drop_index('idx_users_email')
    
    # Drop table
    op.execute("DROP TABLE IF EXISTS users;")