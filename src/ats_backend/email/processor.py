"""Email processing service for resume ingestion."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
import structlog

from ats_backend.email.models import (
    EmailMessage, 
    EmailIngestionResponse, 
    EmailAttachment,
    FileStorageInfo
)
from ats_backend.email.storage import FileStorageService
from ats_backend.services.resume_job_service import ResumeJobService
from ats_backend.schemas.resume_job import ResumeJobCreate
from ats_backend.models.resume_job import ResumeJob

logger = structlog.get_logger(__name__)


class EmailProcessor:
    """Service for processing email messages and creating resume jobs."""
    
    def __init__(self, storage_service: Optional[FileStorageService] = None):
        """Initialize email processor.
        
        Args:
            storage_service: File storage service instance
        """
        self.storage_service = storage_service or FileStorageService()
        self.resume_job_service = ResumeJobService()
    
    def process_email(
        self,
        db: Session,
        client_id: UUID,
        email: EmailMessage,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> EmailIngestionResponse:
        """Process an email message and create resume jobs for attachments.
        
        Args:
            db: Database session
            client_id: Client UUID for multi-tenant isolation
            email: Email message to process
            user_id: User who initiated the processing (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            EmailIngestionResponse with processing results
        """
        try:
            # Check for duplicate email message ID
            existing_job = self.resume_job_service.get_job_by_email_message_id(
                db, email.message_id
            )
            
            if existing_job:
                logger.info(
                    "Duplicate email detected, skipping processing",
                    message_id=email.message_id,
                    existing_job_id=str(existing_job.id),
                    client_id=str(client_id)
                )
                return EmailIngestionResponse(
                    success=True,
                    message="Email already processed (duplicate message ID)",
                    job_ids=[existing_job.id],
                    duplicate_message_id=email.message_id,
                    processed_attachments=0
                )
            
            # Process each attachment
            job_ids = []
            processed_count = 0
            
            for attachment in email.attachments:
                try:
                    # Validate file format
                    if not self.storage_service.validate_file_format(attachment):
                        logger.warning(
                            "Skipping unsupported file format",
                            filename=attachment.filename,
                            content_type=attachment.content_type,
                            message_id=email.message_id
                        )
                        continue
                    
                    # Store attachment to filesystem
                    storage_info = self.storage_service.store_attachment(
                        attachment, str(client_id), email.message_id
                    )
                    
                    # Create resume job
                    job_data = ResumeJobCreate(
                        email_message_id=email.message_id,
                        file_name=attachment.filename,
                        file_path=storage_info.file_path,
                        status="PENDING"
                    )
                    
                    job = self.resume_job_service.create_resume_job(
                        db=db,
                        client_id=client_id,
                        job_data=job_data,
                        user_id=user_id,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    
                    job_ids.append(job.id)
                    processed_count += 1
                    
                    # Trigger resume processing task asynchronously
                    from ats_backend.workers.resume_tasks import process_resume_file
                    process_resume_file.delay(
                        client_id=str(client_id),
                        job_id=str(job.id),
                        user_id=str(user_id) if user_id else None
                    )
                    
                    logger.info(
                        "Resume job created and processing queued",
                        job_id=str(job.id),
                        filename=attachment.filename,
                        message_id=email.message_id,
                        client_id=str(client_id)
                    )
                    
                except Exception as e:
                    logger.error(
                        "Failed to process attachment",
                        filename=attachment.filename,
                        message_id=email.message_id,
                        client_id=str(client_id),
                        error=str(e)
                    )
                    # Continue processing other attachments
                    continue
            
            if processed_count == 0:
                return EmailIngestionResponse(
                    success=False,
                    message="No valid resume attachments found to process",
                    job_ids=[],
                    processed_attachments=0
                )
            
            logger.info(
                "Email processing completed",
                message_id=email.message_id,
                client_id=str(client_id),
                jobs_created=len(job_ids),
                attachments_processed=processed_count
            )
            
            return EmailIngestionResponse(
                success=True,
                message=f"Successfully processed {processed_count} attachments",
                job_ids=job_ids,
                processed_attachments=processed_count
            )
            
        except Exception as e:
            logger.error(
                "Email processing failed",
                message_id=email.message_id,
                client_id=str(client_id),
                error=str(e)
            )
            return EmailIngestionResponse(
                success=False,
                message=f"Email processing failed: {str(e)}",
                job_ids=[],
                processed_attachments=0
            )
    
    def validate_email_message(self, email: EmailMessage) -> List[str]:
        """Validate email message for processing.
        
        Args:
            email: Email message to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        try:
            # Basic validation is handled by Pydantic model
            # Additional business logic validation can be added here
            
            # Check attachment count
            if len(email.attachments) == 0:
                errors.append("Email must contain at least one attachment")
            
            # Check for valid resume attachments
            valid_attachments = 0
            for attachment in email.attachments:
                if self.storage_service.validate_file_format(attachment):
                    valid_attachments += 1
            
            if valid_attachments == 0:
                errors.append("Email must contain at least one valid resume file (PDF, PNG, JPG, TIFF)")
            
            # Check message ID format
            if not email.message_id or len(email.message_id.strip()) == 0:
                errors.append("Email message ID cannot be empty")
            
            # Check sender format
            if not email.sender or '@' not in email.sender:
                errors.append("Invalid sender email address")
            
        except Exception as e:
            errors.append(f"Email validation failed: {str(e)}")
        
        return errors
    
    def get_processing_statistics(
        self,
        db: Session,
        client_id: UUID,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get email processing statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            days_back: Number of days to look back for statistics
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get resume job statistics
            job_stats = self.resume_job_service.get_processing_statistics(db, client_id)
            
            # Get storage statistics
            storage_stats = self.storage_service.get_storage_stats()
            
            # Combine statistics
            stats = {
                "client_id": str(client_id),
                "job_statistics": job_stats,
                "storage_statistics": storage_stats,
                "period_days": days_back,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.debug("Processing statistics generated", client_id=str(client_id), stats=stats)
            return stats
            
        except Exception as e:
            logger.error(
                "Failed to generate processing statistics",
                client_id=str(client_id),
                error=str(e)
            )
            return {
                "client_id": str(client_id),
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }
    
    def cleanup_failed_jobs(
        self,
        db: Session,
        client_id: UUID,
        max_age_hours: int = 24
    ) -> int:
        """Clean up old failed jobs and their associated files.
        
        Args:
            db: Database session
            client_id: Client UUID
            max_age_hours: Maximum age in hours for failed jobs to keep
            
        Returns:
            Number of jobs cleaned up
        """
        try:
            # Get old failed jobs
            failed_jobs = self.resume_job_service.get_failed_jobs(db, client_id, limit=1000)
            
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 60 * 60)
            cleaned_count = 0
            
            for job in failed_jobs:
                if job.created_at.timestamp() < cutoff_time:
                    try:
                        # Delete associated file if exists
                        if job.file_path:
                            self.storage_service.delete_file(job.file_path)
                        
                        # Delete job record
                        self.resume_job_service.delete_job(
                            db, job.id, client_id
                        )
                        
                        cleaned_count += 1
                        
                    except Exception as e:
                        logger.warning(
                            "Failed to clean up failed job",
                            job_id=str(job.id),
                            error=str(e)
                        )
            
            logger.info(
                "Failed jobs cleanup completed",
                client_id=str(client_id),
                jobs_cleaned=cleaned_count,
                max_age_hours=max_age_hours
            )
            
            return cleaned_count
            
        except Exception as e:
            logger.error(
                "Failed jobs cleanup failed",
                client_id=str(client_id),
                error=str(e)
            )
            return 0
    
    def retry_failed_processing(
        self,
        db: Session,
        client_id: UUID,
        job_id: UUID,
        user_id: Optional[UUID] = None
    ) -> bool:
        """Retry processing for a failed job.
        
        Args:
            db: Database session
            client_id: Client UUID
            job_id: Resume job UUID to retry
            user_id: User who initiated the retry (optional)
            
        Returns:
            True if retry was initiated successfully, False otherwise
        """
        try:
            success = self.resume_job_service.retry_failed_job(
                db, job_id, user_id
            )
            
            if success:
                logger.info(
                    "Job retry initiated",
                    job_id=str(job_id),
                    client_id=str(client_id),
                    user_id=str(user_id) if user_id else None
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Job retry failed",
                job_id=str(job_id),
                client_id=str(client_id),
                error=str(e)
            )
            return False