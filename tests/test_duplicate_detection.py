"""Tests for duplicate detection functionality."""

import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import pytest
from uuid import uuid4
from sqlalchemy import create_engine, JSON
from sqlalchemy.orm import sessionmaker

from ats_backend.core.database import Base
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate
from ats_backend.models.application import Application
from ats_backend.services.duplicate_detection_service import DuplicateDetectionService
from ats_backend.resume.hash_generator import CandidateHashGenerator


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Monkey patch JSONB to JSON for SQLite compatibility
    from sqlalchemy.dialects.postgresql import JSONB
    import sqlalchemy.dialects.postgresql
    sqlalchemy.dialects.postgresql.JSONB = JSON
    
    # Also patch the models directly before creating tables
    from ats_backend.models.candidate import Candidate
    from ats_backend.core.audit import AuditLog
    
    # Store original column types
    original_skills = Candidate.__table__.columns['skills'].type
    original_experience = Candidate.__table__.columns['experience'].type
    
    # Replace JSONB with JSON for SQLite
    Candidate.__table__.columns['skills'].type = JSON()
    Candidate.__table__.columns['experience'].type = JSON()
    
    try:
        # Also patch AuditLog if it exists
        original_old_values = AuditLog.__table__.columns['old_values'].type
        original_new_values = AuditLog.__table__.columns['new_values'].type
        original_changes = AuditLog.__table__.columns['changes'].type
        
        AuditLog.__table__.columns['old_values'].type = JSON()
        AuditLog.__table__.columns['new_values'].type = JSON()
        AuditLog.__table__.columns['changes'].type = JSON()
    except (AttributeError, KeyError):
        # AuditLog might not be available or have these columns
        pass
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        
        # Restore original column types
        Candidate.__table__.columns['skills'].type = original_skills
        Candidate.__table__.columns['experience'].type = original_experience
        
        try:
            AuditLog.__table__.columns['old_values'].type = original_old_values
            AuditLog.__table__.columns['new_values'].type = original_new_values
            AuditLog.__table__.columns['changes'].type = original_changes
        except (AttributeError, KeyError, NameError):
            pass


@pytest.fixture
def test_client(db_session):
    """Create a test client."""
    client = Client(
        id=uuid4(),
        name="Test Company",
        email_domain="testcompany.com"
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


class TestCandidateHashGenerator:
    """Test candidate hash generation functionality."""
    
    def test_hash_generation_consistency(self):
        """Test that hash generation is consistent for same input."""
        generator = CandidateHashGenerator()
        
        candidate_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+1-555-123-4567"
        }
        
        hash1 = generator.generate_hash_from_dict(candidate_data)
        hash2 = generator.generate_hash_from_dict(candidate_data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string length
    
    def test_name_normalization(self):
        """Test name normalization for consistent hashing."""
        generator = CandidateHashGenerator()
        
        # Different formats of the same name should produce same normalized result
        names = [
            "John Doe",
            "john doe",
            "JOHN DOE",
            "  John   Doe  ",
            "Mr. John Doe",
            "John Doe Jr."
        ]
        
        normalized_names = [generator._normalize_name(name) for name in names]
        
        # All should normalize to the same base name
        base_name = "john doe"
        for normalized in normalized_names:
            assert base_name in normalized or normalized == base_name
    
    def test_email_normalization(self):
        """Test email normalization for consistent hashing."""
        generator = CandidateHashGenerator()
        
        # Gmail dot and plus addressing normalization
        emails = [
            "john.doe@gmail.com",
            "johndoe@gmail.com",
            "john.doe+test@gmail.com",
            "johndoe+work@gmail.com"
        ]
        
        normalized_emails = [generator._normalize_email(email) for email in emails]
        
        # All Gmail addresses should normalize to the same base
        assert normalized_emails[0] == normalized_emails[1]  # Dots removed
        assert normalized_emails[2] == normalized_emails[3]  # Plus addressing removed
        assert normalized_emails[0] == normalized_emails[2]  # Both normalizations
    
    def test_phone_normalization(self):
        """Test phone number normalization for consistent hashing."""
        generator = CandidateHashGenerator()
        
        # Different formats of the same Indian phone number
        phones = [
            "+91-9876543210",
            "91-9876543210",
            "091-9876543210",
            "9876543210",
            "+91 9876 543 210",
            "(91) 9876-543-210"
        ]
        
        normalized_phones = [generator._normalize_phone(phone) for phone in phones]
        
        # All should normalize to the same format
        expected = "919876543210"
        for normalized in normalized_phones:
            assert normalized == expected
    
    def test_similarity_calculation(self):
        """Test similarity score calculation between candidates."""
        generator = CandidateHashGenerator()
        
        candidate1 = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "9876543210"
        }
        
        # Exact match
        candidate2 = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "9876543210"
        }
        
        similarity = generator.calculate_similarity_score(candidate1, candidate2)
        assert similarity == 1.0
        
        # Partial match (same name, different email)
        candidate3 = {
            "name": "John Doe",
            "email": "john.smith@example.com",
            "phone": "9876543210"
        }
        
        similarity = generator.calculate_similarity_score(candidate1, candidate3)
        assert 0.6 < similarity < 1.0  # Should be high but not perfect
        
        # No match
        candidate4 = {
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
            "phone": "1234567890"
        }
        
        similarity = generator.calculate_similarity_score(candidate1, candidate4)
        assert similarity < 0.3  # Should be low


class TestDuplicateDetectionService:
    """Test duplicate detection service functionality."""
    
    def test_duplicate_detection_no_matches(self, db_session, test_client):
        """Test duplicate detection when no matches exist."""
        service = DuplicateDetectionService()
        
        candidate_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "9876543210"
        }
        
        result = service.detect_duplicates(
            db=db_session,
            client_id=test_client.id,
            candidate_data=candidate_data
        )
        
        assert not result.has_duplicates
        assert len(result.matches) == 0
        assert not result.should_flag
        assert result.flag_reason is None
        assert len(result.candidate_hash) == 64
    
    def test_duplicate_detection_with_existing_candidate(self, db_session, test_client):
        """Test duplicate detection when similar candidate exists."""
        service = DuplicateDetectionService()
        
        # Create an existing candidate
        existing_candidate = Candidate(
            id=uuid4(),
            client_id=test_client.id,
            name="John Doe",
            email="john.doe@example.com",
            phone="9876543210",
            status="ACTIVE"
        )
        db_session.add(existing_candidate)
        db_session.commit()
        
        # Update hash for existing candidate
        service.update_candidate_hash(db_session, existing_candidate.id)
        
        # Test with very similar candidate data
        candidate_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "9876543210"
        }
        
        result = service.detect_duplicates(
            db=db_session,
            client_id=test_client.id,
            candidate_data=candidate_data
        )
        
        assert result.has_duplicates
        assert len(result.matches) > 0
        assert result.matches[0].similarity_score >= 0.8
        assert result.matches[0].candidate.id == existing_candidate.id
    
    def test_duplicate_detection_left_status_flagging(self, db_session, test_client):
        """Test that candidates with LEFT status are flagged for review."""
        service = DuplicateDetectionService()
        
        # Create an existing candidate with LEFT status
        existing_candidate = Candidate(
            id=uuid4(),
            client_id=test_client.id,
            name="John Doe",
            email="john.doe@example.com",
            phone="9876543210",
            status="LEFT"  # This should trigger flagging
        )
        db_session.add(existing_candidate)
        db_session.commit()
        
        # Update hash for existing candidate
        service.update_candidate_hash(db_session, existing_candidate.id)
        
        # Test with similar candidate data
        candidate_data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "9876543210"
        }
        
        result = service.detect_duplicates(
            db=db_session,
            client_id=test_client.id,
            candidate_data=candidate_data
        )
        
        assert result.has_duplicates
        assert result.should_flag
        assert "LEFT status" in result.flag_reason
        assert len(result.matches) > 0
        assert result.matches[0].candidate.status == "LEFT"
    
    def test_workflow_progression_control(self, db_session, test_client):
        """Test workflow progression control for flagged applications."""
        service = DuplicateDetectionService()
        
        # Create a candidate and application
        candidate = Candidate(
            id=uuid4(),
            client_id=test_client.id,
            name="John Doe",
            email="john.doe@example.com",
            phone="9876543210",
            status="ACTIVE"
        )
        db_session.add(candidate)
        db_session.commit()
        
        # Create a flagged application
        application = Application(
            id=uuid4(),
            client_id=test_client.id,
            candidate_id=candidate.id,
            job_title="Software Engineer",
            status="RECEIVED",
            flagged_for_review=True,
            flag_reason="Potential duplicate with LEFT status"
        )
        db_session.add(application)
        db_session.commit()
        
        # Test workflow progression check
        is_allowed, reason = service.check_workflow_progression_allowed(
            db=db_session,
            application_id=application.id
        )
        
        assert not is_allowed
        assert "flagged for review" in reason.lower()
    
    def test_batch_hash_update(self, db_session, test_client):
        """Test batch hash update functionality."""
        service = DuplicateDetectionService()
        
        # Create multiple candidates without hashes
        candidates = []
        for i in range(3):
            candidate = Candidate(
                id=uuid4(),
                client_id=test_client.id,
                name=f"Test User {i}",
                email=f"user{i}@example.com",
                phone=f"987654321{i}",
                status="ACTIVE",
                candidate_hash=None  # No hash initially
            )
            candidates.append(candidate)
            db_session.add(candidate)
        
        db_session.commit()
        
        # Run batch hash update
        stats = service.batch_update_candidate_hashes(
            db=db_session,
            client_id=test_client.id,
            force_regenerate=False
        )
        
        assert stats["total_candidates"] == 3
        assert stats["updated"] == 3
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        
        # Verify hashes were created
        db_session.refresh(candidates[0])
        assert candidates[0].candidate_hash is not None
        assert len(candidates[0].candidate_hash) == 64
    
    def test_duplicate_statistics(self, db_session, test_client):
        """Test duplicate detection statistics."""
        service = DuplicateDetectionService()
        
        # Create candidates with different statuses
        candidates = [
            Candidate(
                id=uuid4(),
                client_id=test_client.id,
                name="Active User",
                email="active@example.com",
                phone="9876543210",
                status="ACTIVE",
                candidate_hash="hash1"
            ),
            Candidate(
                id=uuid4(),
                client_id=test_client.id,
                name="Left User",
                email="left@example.com",
                phone="9876543211",
                status="LEFT",
                candidate_hash="hash2"
            ),
            Candidate(
                id=uuid4(),
                client_id=test_client.id,
                name="No Hash User",
                email="nohash@example.com",
                phone="9876543212",
                status="ACTIVE",
                candidate_hash=None
            )
        ]
        
        for candidate in candidates:
            db_session.add(candidate)
        db_session.commit()
        
        # Create a flagged application
        application = Application(
            id=uuid4(),
            client_id=test_client.id,
            candidate_id=candidates[0].id,
            job_title="Test Job",
            status="RECEIVED",
            flagged_for_review=True,
            flag_reason="Test flag"
        )
        db_session.add(application)
        db_session.commit()
        
        # Get statistics
        stats = service.get_duplicate_statistics(
            db=db_session,
            client_id=test_client.id
        )
        
        assert stats["total_candidates"] == 3
        assert stats["candidates_with_hash"] == 2
        assert stats["candidates_without_hash"] == 1
        assert stats["left_status_candidates"] == 1
        assert stats["flagged_applications"] == 1
        assert abs(stats["hash_coverage_percentage"] - 66.7) < 0.1  # 2/3 * 100


if __name__ == "__main__":
    pytest.main([__file__])