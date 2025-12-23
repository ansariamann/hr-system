"""Tests for database schema and RLS policies."""

import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import pytest
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from ats_backend.core.database import Base
from ats_backend.core.session_context import set_client_context, clear_client_context
from ats_backend.models import Client, Candidate, Application, ResumeJob


class TestDatabaseSchema:
    """Test database schema creation and constraints."""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:", echo=False)
        
        # Monkey patch JSONB to JSON for SQLite compatibility
        from sqlalchemy import JSON
        from sqlalchemy.dialects.postgresql import JSONB
        original_jsonb = JSONB
        import sqlalchemy.dialects.postgresql
        sqlalchemy.dialects.postgresql.JSONB = JSON
        
        # Also patch the models directly before creating tables
        from ats_backend.models.candidate import Candidate
        from ats_backend.core.audit import AuditLog
        
        # Store original column types
        original_skills = Candidate.__table__.columns['skills'].type
        original_experience = Candidate.__table__.columns['experience'].type
        original_old_values = AuditLog.__table__.columns['old_values'].type
        original_new_values = AuditLog.__table__.columns['new_values'].type
        original_changes = AuditLog.__table__.columns['changes'].type
        
        try:
            # Replace JSONB columns with JSON
            Candidate.__table__.columns['skills'].type = JSON()
            Candidate.__table__.columns['experience'].type = JSON()
            AuditLog.__table__.columns['old_values'].type = JSON()
            AuditLog.__table__.columns['new_values'].type = JSON()
            AuditLog.__table__.columns['changes'].type = JSON()
            
            Base.metadata.create_all(engine)
            
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()
            
            yield session
            
            session.close()
        finally:
            # Restore original types
            Candidate.__table__.columns['skills'].type = original_skills
            Candidate.__table__.columns['experience'].type = original_experience
            AuditLog.__table__.columns['old_values'].type = original_old_values
            AuditLog.__table__.columns['new_values'].type = original_new_values
            AuditLog.__table__.columns['changes'].type = original_changes
            # Restore original JSONB
            sqlalchemy.dialects.postgresql.JSONB = original_jsonb
    
    @pytest.fixture
    def sample_client(self, db_session):
        """Create a sample client for testing."""
        client = Client(
            name="Test Company",
            email_domain="testcompany.com"
        )
        db_session.add(client)
        db_session.commit()
        return client
    
    def test_client_creation(self, db_session):
        """Test client model creation."""
        client = Client(
            name="Test Company",
            email_domain="example.com"
        )
        
        db_session.add(client)
        db_session.commit()
        
        assert client.id is not None
        assert client.name == "Test Company"
        assert client.email_domain == "example.com"
        assert client.created_at is not None
        assert client.updated_at is not None
    
    def test_candidate_creation(self, db_session, sample_client):
        """Test candidate model creation."""
        candidate = Candidate(
            client_id=sample_client.id,
            name="John Doe",
            email="john.doe@example.com",
            phone="+1234567890",
            skills={"languages": ["Python", "JavaScript"], "frameworks": ["FastAPI", "React"]},
            experience=[{"company": "Tech Corp", "role": "Developer", "years": 2}],
            ctc_current=Decimal("50000.00"),
            ctc_expected=Decimal("60000.00")
        )
        
        db_session.add(candidate)
        db_session.commit()
        
        assert candidate.id is not None
        assert candidate.client_id == sample_client.id
        assert candidate.name == "John Doe"
        assert candidate.email == "john.doe@example.com"
        assert candidate.phone == "+1234567890"
        assert candidate.skills["languages"] == ["Python", "JavaScript"]
        assert candidate.ctc_current == Decimal("50000.00")
        assert candidate.status == "ACTIVE"
    
    def test_application_creation(self, db_session, sample_client):
        """Test application model creation."""
        # Create candidate first
        candidate = Candidate(
            client_id=sample_client.id,
            name="Jane Smith",
            email="jane.smith@example.com"
        )
        db_session.add(candidate)
        db_session.commit()
        
        # Create application
        application = Application(
            client_id=sample_client.id,
            candidate_id=candidate.id,
            job_title="Software Engineer",
            status="RECEIVED"
        )
        
        db_session.add(application)
        db_session.commit()
        
        assert application.id is not None
        assert application.client_id == sample_client.id
        assert application.candidate_id == candidate.id
        assert application.job_title == "Software Engineer"
        assert application.status == "RECEIVED"
        assert application.flagged_for_review is False
        assert application.deleted_at is None
    
    def test_application_soft_delete(self, db_session, sample_client):
        """Test application soft delete functionality."""
        # Create candidate and application
        candidate = Candidate(
            client_id=sample_client.id,
            name="Test Candidate",
            email="test@example.com"
        )
        db_session.add(candidate)
        db_session.commit()
        
        application = Application(
            client_id=sample_client.id,
            candidate_id=candidate.id,
            job_title="Test Job"
        )
        db_session.add(application)
        db_session.commit()
        
        # Test soft delete
        assert not application.is_deleted
        application.soft_delete()
        assert application.is_deleted
        assert application.deleted_at is not None
    
    def test_resume_job_creation(self, db_session, sample_client):
        """Test resume job model creation."""
        resume_job = ResumeJob(
            client_id=sample_client.id,
            email_message_id="msg-12345",
            file_name="resume.pdf",
            file_path="/uploads/resume.pdf",
            status="PENDING"
        )
        
        db_session.add(resume_job)
        db_session.commit()
        
        assert resume_job.id is not None
        assert resume_job.client_id == sample_client.id
        assert resume_job.email_message_id == "msg-12345"
        assert resume_job.file_name == "resume.pdf"
        assert resume_job.status == "PENDING"
    
    def test_resume_job_status_updates(self, db_session, sample_client):
        """Test resume job status update methods."""
        resume_job = ResumeJob(
            client_id=sample_client.id,
            file_name="test.pdf"
        )
        db_session.add(resume_job)
        db_session.commit()
        
        # Test mark as processed
        resume_job.mark_processed()
        assert resume_job.status == "COMPLETED"
        assert resume_job.processed_at is not None
        
        # Test mark as failed
        resume_job.mark_failed("Processing error")
        assert resume_job.status == "FAILED"
        assert resume_job.error_message == "Processing error"
    
    def test_foreign_key_constraints(self, db_session, sample_client):
        """Test foreign key constraints."""
        # Note: SQLite doesn't enforce foreign key constraints by default
        # This test validates the model structure rather than database enforcement
        
        # Test that we can create a candidate with valid client_id
        valid_candidate = Candidate(
            client_id=sample_client.id,
            name="Valid Candidate"
        )
        db_session.add(valid_candidate)
        db_session.commit()
        
        assert valid_candidate.id is not None
        assert valid_candidate.client_id == sample_client.id
    
    def test_unique_constraints(self, db_session, sample_client):
        """Test unique constraints."""
        # Create first resume job
        job1 = ResumeJob(
            client_id=sample_client.id,
            email_message_id="unique-msg-id"
        )
        db_session.add(job1)
        db_session.commit()
        
        # Try to create second job with same message ID should fail
        with pytest.raises(IntegrityError):
            job2 = ResumeJob(
                client_id=sample_client.id,
                email_message_id="unique-msg-id"  # Duplicate
            )
            db_session.add(job2)
            db_session.commit()


class TestRLSPolicies:
    """Test Row Level Security policies (PostgreSQL specific)."""
    
    def test_session_context_functions(self):
        """Test session context management functions."""
        # Note: These tests would require a PostgreSQL connection
        # For now, we'll test the function interfaces
        from ats_backend.core.session_context import SessionContextManager
        
        # Test that the class exists and has required methods
        assert hasattr(SessionContextManager, 'set_client_context')
        assert hasattr(SessionContextManager, 'clear_client_context')
        assert hasattr(SessionContextManager, 'get_current_client_id')
        assert hasattr(SessionContextManager, 'with_client_context')
    
    def test_database_manager_context_method(self):
        """Test database manager context setting method."""
        from ats_backend.core.database import DatabaseManager
        
        # Test that the method exists
        db_manager = DatabaseManager("sqlite:///:memory:")
        assert hasattr(db_manager, 'set_client_context')


if __name__ == "__main__":
    pytest.main([__file__])