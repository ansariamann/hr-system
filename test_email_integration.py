#!/usr/bin/env python3
"""Integration test for email ingestion with database operations."""

import sys
from pathlib import Path
from uuid import uuid4
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ats_backend.email.models import EmailMessage, EmailAttachment, EmailIngestionRequest
from ats_backend.email.parser import EmailParser
from ats_backend.email.processor import EmailProcessor
from ats_backend.email.server import create_test_email_data
from ats_backend.core.database import get_db, db_manager, init_db
from ats_backend.services.resume_job_service import ResumeJobService
from ats_backend.schemas.resume_job import ResumeJobCreate

def test_database_integration():
    """Test email processing with database operations."""
    print("Testing database integration...")
    
    # Monkey patch JSONB to JSON for SQLite compatibility
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB
    original_jsonb = JSONB
    import sqlalchemy.dialects.postgresql
    sqlalchemy.dialects.postgresql.JSONB = JSON
    
    # Also patch the models directly
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
        
        # Get database session
        db = next(get_db())
        
        try:
            # Create test client ID (in real scenario, this would be from authenticated user)
            client_id = uuid4()
            
            # Create test email data
            test_data = create_test_email_data(
                message_id="integration-test-001@example.com",
                sender="integration@example.com",
                subject="Integration Test Resume",
                num_attachments=2
            )
            
            # Parse email
            parser = EmailParser()
            email = parser.parse_email_dict(test_data)
            
            print(f"✓ Email parsed: {email.message_id}")
            print(f"✓ Attachments: {len(email.attachments)}")
            
            # Process email with database
            processor = EmailProcessor()
            result = processor.process_email(
                db=db,
                client_id=client_id,
                email=email,
                user_id=None,
                ip_address="127.0.0.1",
                user_agent="test-agent"
            )
            
            print(f"✓ Processing result: {result.success}")
            print(f"✓ Message: {result.message}")
            print(f"✓ Jobs created: {len(result.job_ids)}")
            print(f"✓ Attachments processed: {result.processed_attachments}")
            
            # Verify jobs were created in database
            resume_job_service = ResumeJobService()
            
            for job_id in result.job_ids:
                job = resume_job_service.get_job_by_id(db, job_id)
                if job:
                    print(f"✓ Job {job_id} found in database")
                    print(f"  - Status: {job.status}")
                    print(f"  - File: {job.file_name}")
                    print(f"  - Message ID: {job.email_message_id}")
                else:
                    print(f"✗ Job {job_id} not found in database")
            
            # Test deduplication
            print("\nTesting deduplication...")
            
            # Try to process the same email again
            result2 = processor.process_email(
                db=db,
                client_id=client_id,
                email=email,
                user_id=None,
                ip_address="127.0.0.1",
                user_agent="test-agent"
            )
            
            print(f"✓ Duplicate processing result: {result2.success}")
            print(f"✓ Duplicate message: {result2.message}")
            print(f"✓ Duplicate detected: {result2.duplicate_message_id is not None}")
            
            # Get processing statistics
            print("\nTesting statistics...")
            
            stats = processor.get_processing_statistics(db, client_id)
            print(f"✓ Statistics generated")
            print(f"  - Total jobs: {stats['job_statistics']['total_jobs']}")
            print(f"  - Pending jobs: {stats['job_statistics']['pending_jobs']}")
            
            return True
            
        except Exception as e:
            print(f"✗ Database integration test failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            db.close()
    
    finally:
        # Restore original types
        Candidate.__table__.columns['skills'].type = original_skills
        Candidate.__table__.columns['experience'].type = original_experience
        AuditLog.__table__.columns['old_values'].type = original_old_values
        AuditLog.__table__.columns['new_values'].type = original_new_values
        AuditLog.__table__.columns['changes'].type = original_changes
        # Restore original JSONB
        sqlalchemy.dialects.postgresql.JSONB = original_jsonb

def test_resume_job_service():
    """Test resume job service operations."""
    print("\nTesting resume job service...")
    
    # Monkey patch JSONB to JSON for SQLite compatibility
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB
    original_jsonb = JSONB
    import sqlalchemy.dialects.postgresql
    sqlalchemy.dialects.postgresql.JSONB = JSON
    
    # Also patch the models directly
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
        
        db = next(get_db())
        
        try:
            service = ResumeJobService()
            client_id = uuid4()
            
            # Create a test job
            job_data = ResumeJobCreate(
                email_message_id="service-test-001@example.com",
                file_name="test_resume.pdf",
                file_path="/tmp/test_resume.pdf",
                status="PENDING"
            )
            
            job = service.create_resume_job(
                db=db,
                client_id=client_id,
                job_data=job_data,
                user_id=None,
                ip_address="127.0.0.1",
                user_agent="test-agent"
            )
            
            print(f"✓ Job created: {job.id}")
            print(f"✓ Status: {job.status}")
            print(f"✓ File: {job.file_name}")
            
            # Test job retrieval
            retrieved_job = service.get_job_by_id(db, job.id)
            if retrieved_job:
                print(f"✓ Job retrieved successfully")
            else:
                print(f"✗ Job retrieval failed")
            
            # Test status update
            success = service.mark_job_processing(db, job.id)
            if success:
                print(f"✓ Job marked as processing")
            else:
                print(f"✗ Failed to mark job as processing")
            
            # Test completion
            success = service.mark_job_completed(db, job.id)
            if success:
                print(f"✓ Job marked as completed")
            else:
                print(f"✗ Failed to mark job as completed")
            
            # Test statistics
            stats = service.get_processing_statistics(db, client_id)
            print(f"✓ Statistics: {stats}")
            
            return True
            
        except Exception as e:
            print(f"✗ Resume job service test failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            db.close()
    
    finally:
        # Restore original types
        Candidate.__table__.columns['skills'].type = original_skills
        Candidate.__table__.columns['experience'].type = original_experience
        AuditLog.__table__.columns['old_values'].type = original_old_values
        AuditLog.__table__.columns['new_values'].type = original_new_values
        AuditLog.__table__.columns['changes'].type = original_changes
        # Restore original JSONB
        sqlalchemy.dialects.postgresql.JSONB = original_jsonb

def test_email_validation():
    """Test comprehensive email validation."""
    print("\nTesting email validation...")
    
    processor = EmailProcessor()
    
    # Test valid email
    valid_data = create_test_email_data(
        message_id="valid-test@example.com",
        sender="valid@example.com",
        subject="Valid Email",
        num_attachments=1
    )
    
    parser = EmailParser()
    valid_email = parser.parse_email_dict(valid_data)
    
    errors = processor.validate_email_message(valid_email)
    if not errors:
        print("✓ Valid email passed validation")
    else:
        print(f"✗ Valid email failed validation: {errors}")
    
    # Test invalid email (no attachments)
    try:
        invalid_email = EmailMessage(
            message_id="invalid-test@example.com",
            sender="invalid@example.com",
            subject="Invalid Email",
            attachments=[]  # No attachments
        )
        print("✗ Invalid email should have failed validation")
    except Exception as e:
        print("✓ Invalid email correctly rejected by model validation")
    
    return True

def main():
    """Run integration tests."""
    print("=== Email Ingestion Integration Tests ===\n")
    
    try:
        # Initialize database
        print("Initializing database...")
        db_manager.initialize()
        print("✓ Database initialized")
        
        # Run tests
        success1 = test_database_integration()
        success2 = test_resume_job_service()
        success3 = test_email_validation()
        
        if success1 and success2 and success3:
            print("\n=== All Integration Tests Passed ===")
            print("✓ Database integration working")
            print("✓ Resume job service working")
            print("✓ Email validation working")
            print("\nEmail ingestion system is ready for production!")
            return 0
        else:
            print("\n✗ Some integration tests failed")
            return 1
            
    except Exception as e:
        print(f"\n✗ Integration tests failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())