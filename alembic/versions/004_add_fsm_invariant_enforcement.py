"""Add FSM invariant enforcement with database constraints

Revision ID: 004
Revises: 003
Create Date: 2025-12-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add FSM invariant enforcement with database constraints."""
    
    # Add is_blacklisted column to candidates table
    op.add_column('candidates', sa.Column('is_blacklisted', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create FSM transition log table for comprehensive state transition audit logging
    op.execute("""
        CREATE TABLE fsm_transition_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES candidates(id),
            old_status VARCHAR(50) NOT NULL,
            new_status VARCHAR(50) NOT NULL,
            actor_id UUID,
            actor_type VARCHAR(20) NOT NULL DEFAULT 'SYSTEM',
            reason TEXT NOT NULL,
            is_terminal BOOLEAN DEFAULT FALSE,
            client_id UUID NOT NULL REFERENCES clients(id),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create indexes for FSM transition logs
    op.create_index('idx_fsm_transition_logs_candidate_id', 'fsm_transition_logs', ['candidate_id'])
    op.create_index('idx_fsm_transition_logs_client_id', 'fsm_transition_logs', ['client_id'])
    op.create_index('idx_fsm_transition_logs_created_at', 'fsm_transition_logs', ['created_at'])
    
    # Enable RLS on FSM transition logs
    op.execute("ALTER TABLE fsm_transition_logs ENABLE ROW LEVEL SECURITY;")
    
    # Create RLS policy for FSM transition logs
    op.execute("""
        CREATE POLICY client_isolation_fsm_transition_logs ON fsm_transition_logs
            FOR ALL TO authenticated_users
            USING (client_id = current_setting('app.current_client_id', true)::UUID);
    """)
    
    # Add database constraint: LEFT_COMPANY implies blacklisted (Requirement 3.1)
    op.execute("""
        ALTER TABLE candidates
        ADD CONSTRAINT check_left_company_blacklisted
        CHECK (status != 'LEFT_COMPANY' OR is_blacklisted = TRUE);
    """)
    
    # Create function to validate state transitions and prevent skipping JOINED state (Requirement 3.2)
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_candidate_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Prevent skipping JOINED state when transitioning to LEFT_COMPANY
            IF OLD.status = 'ACTIVE' AND NEW.status = 'LEFT_COMPANY' THEN
                -- Must have been JOINED first - check FSM transition logs
                IF NOT EXISTS (
                    SELECT 1 FROM fsm_transition_logs
                    WHERE candidate_id = NEW.id
                    AND new_status = 'JOINED'
                ) THEN
                    RAISE EXCEPTION 'Cannot transition from ACTIVE to LEFT_COMPANY without first transitioning to JOINED state';
                END IF;
            END IF;
            
            -- Enforce terminal state: no transitions allowed from LEFT_COMPANY (Requirement 3.3)
            IF OLD.status = 'LEFT_COMPANY' AND NEW.status != 'LEFT_COMPANY' THEN
                RAISE EXCEPTION 'LEFT_COMPANY is a terminal state - no further transitions allowed';
            END IF;
            
            -- When transitioning to LEFT_COMPANY, automatically set is_blacklisted to TRUE
            IF NEW.status = 'LEFT_COMPANY' THEN
                NEW.is_blacklisted = TRUE;
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for candidate status transition validation
    op.execute("""
        CREATE TRIGGER candidate_status_transition_trigger
            BEFORE UPDATE ON candidates
            FOR EACH ROW
            WHEN (OLD.status IS DISTINCT FROM NEW.status)
            EXECUTE FUNCTION validate_candidate_status_transition();
    """)
    
    # Create function to prevent modification of protected fields (Requirement 3.4)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_protected_field_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Prevent client modification of skills, candidate core profile, and blacklist flag
            -- Allow system modifications (when actor_type is SYSTEM in context)
            
            -- Check if this is a system modification by looking for a special session variable
            IF current_setting('app.allow_protected_field_modification', true) != 'true' THEN
                -- Prevent modification of skills
                IF OLD.skills IS DISTINCT FROM NEW.skills THEN
                    RAISE EXCEPTION 'Modification of candidate skills is not allowed';
                END IF;
                
                -- Prevent modification of core profile fields (name, email, phone)
                IF OLD.name IS DISTINCT FROM NEW.name THEN
                    RAISE EXCEPTION 'Modification of candidate name is not allowed';
                END IF;
                
                IF OLD.email IS DISTINCT FROM NEW.email THEN
                    RAISE EXCEPTION 'Modification of candidate email is not allowed';
                END IF;
                
                IF OLD.phone IS DISTINCT FROM NEW.phone THEN
                    RAISE EXCEPTION 'Modification of candidate phone is not allowed';
                END IF;
                
                -- Prevent modification of blacklist flag
                IF OLD.is_blacklisted IS DISTINCT FROM NEW.is_blacklisted THEN
                    RAISE EXCEPTION 'Modification of candidate blacklist status is not allowed';
                END IF;
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for protected field modification prevention
    op.execute("""
        CREATE TRIGGER prevent_protected_field_modification_trigger
            BEFORE UPDATE ON candidates
            FOR EACH ROW
            EXECUTE FUNCTION prevent_protected_field_modification();
    """)
    
    # Create function to log FSM transitions (Requirement 3.5)
    op.execute("""
        CREATE OR REPLACE FUNCTION log_fsm_transition()
        RETURNS TRIGGER AS $$
        DECLARE
            actor_id_val UUID;
            actor_type_val VARCHAR(20);
            reason_val TEXT;
        BEGIN
            -- Get actor information from session variables
            actor_id_val := current_setting('app.current_user_id', true)::UUID;
            actor_type_val := COALESCE(current_setting('app.actor_type', true), 'SYSTEM');
            reason_val := COALESCE(current_setting('app.transition_reason', true), 'Status transition');
            
            -- Log the transition
            INSERT INTO fsm_transition_logs (
                candidate_id,
                old_status,
                new_status,
                actor_id,
                actor_type,
                reason,
                is_terminal,
                client_id
            ) VALUES (
                NEW.id,
                OLD.status,
                NEW.status,
                actor_id_val,
                actor_type_val,
                reason_val,
                NEW.status = 'LEFT_COMPANY',
                NEW.client_id
            );
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for FSM transition logging
    op.execute("""
        CREATE TRIGGER log_fsm_transition_trigger
            AFTER UPDATE ON candidates
            FOR EACH ROW
            WHEN (OLD.status IS DISTINCT FROM NEW.status)
            EXECUTE FUNCTION log_fsm_transition();
    """)


def downgrade() -> None:
    """Remove FSM invariant enforcement."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS log_fsm_transition_trigger ON candidates;")
    op.execute("DROP TRIGGER IF EXISTS prevent_protected_field_modification_trigger ON candidates;")
    op.execute("DROP TRIGGER IF EXISTS candidate_status_transition_trigger ON candidates;")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS log_fsm_transition();")
    op.execute("DROP FUNCTION IF EXISTS prevent_protected_field_modification();")
    op.execute("DROP FUNCTION IF EXISTS validate_candidate_status_transition();")
    
    # Drop constraint
    op.execute("ALTER TABLE candidates DROP CONSTRAINT IF EXISTS check_left_company_blacklisted;")
    
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS client_isolation_fsm_transition_logs ON fsm_transition_logs;")
    
    # Disable RLS
    op.execute("ALTER TABLE fsm_transition_logs DISABLE ROW LEVEL SECURITY;")
    
    # Drop indexes
    op.drop_index('idx_fsm_transition_logs_created_at')
    op.drop_index('idx_fsm_transition_logs_client_id')
    op.drop_index('idx_fsm_transition_logs_candidate_id')
    
    # Drop FSM transition logs table
    op.execute("DROP TABLE IF EXISTS fsm_transition_logs;")
    
    # Remove is_blacklisted column
    op.drop_column('candidates', 'is_blacklisted')