"""Resume job management service."""

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.resume_job import ResumeJob
from ats_backend.repositories.resume_job import ResumeJobRepository
from ats_backend.schemas.resume_job import ResumeJobCreate, ResumeJobUpdate

logger = structlog.get_logger(__name__)


class ResumeJobService:
    """Service for managing resume job operations."""
    
    def __init__(self):
        self.repository = ResumeJobRepository()
    
    def create_resume_job(
        self,
        db: Session,
        client_id: UUID,
        job_data: ResumeJobCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ResumeJob:
        """Create a new resume job with audit logging.
        
        Args:
            db: Database session
            client_id: Client UUID
            job_data: Resume job creation data
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created resume job
            
        Raises:
            ValueError: If resume job creation fails
        """
        try:
            # Check for duplicate email message ID if provided
            if job_data.email_message_id:
                existing_job = self.repository.get_by_email_message_id(
                    db, job_data.email_message_id
                )
                if existing_job:
                    logger.info(
                        "Duplicate resume job detected",
                        email_message_id=job_data.email_message_id,
                        existing_job_id=str(existing_job.id)
                    )
                    return existing_job
            
            job = self.repository.create_with_audit(
                db=db,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **job_data.dict()
            )
            
            logger.info(
                "Resume job created",
                job_id=str(job.id),
                client_id=str(client_id),
                file_name=job.file_name,
                status=job.status
            )
            return job
            
        except Exception as e:
            logger.error(
                "Resume job creation failed",
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to create resume job: {str(e)}")
    
    def get_job_by_id(
        self, 
        db: Session, 
        job_id: UUID
    ) -> Optional[ResumeJob]:
        """Get resume job by ID.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            
        Returns:
            Resume job if found, None otherwise
        """
        return self.repository.get_by_id(db, job_id)
    
    def get_job_by_email_message_id(
        self, 
        db: Session, 
        email_message_id: str
    ) -> Optional[ResumeJob]:
        """Get resume job by email message ID for deduplication.
        
        Args:
            db: Database session
            email_message_id: Email message ID
            
        Returns:
            Resume job if found, None otherwise
        """
        return self.repository.get_by_email_message_id(db, email_message_id)
    
    def get_jobs_by_status(
        self,
        db: Session,
        client_id: UUID,
        status: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[ResumeJob]:
        """Get resume jobs by status within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            status: Job status
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of resume jobs with specified status
        """
        return self.repository.get_by_status(db, client_id, status, skip, limit)
    
    def get_pending_jobs(
        self, 
        db: Session, 
        limit: int = 100
    ) -> List[ResumeJob]:
        """Get pending resume jobs across all clients for processing.
        
        Args:
            db: Database session
            limit: Maximum number of jobs to return
            
        Returns:
            List of pending resume jobs
        """
        return self.repository.get_pending_jobs(db, limit)
    
    def get_failed_jobs(
        self,
        db: Session,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[ResumeJob]:
        """Get failed resume jobs within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of failed resume jobs
        """
        return self.repository.get_failed_jobs(db, client_id, skip, limit)
    
    def update_job_status(
        self,
        db: Session,
        job_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ResumeJob]:
        """Update resume job status with audit logging.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            status: New job status
            error_message: Error message if status is FAILED (optional)
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Updated resume job if found, None otherwise
        """
        try:
            job_data = ResumeJobUpdate(
                status=status,
                error_message=error_message
            )
            
            # Only update fields that are provided
            update_data = job_data.dict(exclude_unset=True)
            
            job = self.repository.update_with_audit(
                db=db,
                id=job_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **update_data
            )
            
            if job:
                logger.info(
                    "Resume job status updated",
                    job_id=str(job_id),
                    status=status,
                    error_message=error_message
                )
            
            return job
            
        except Exception as e:
            logger.error(
                "Resume job status update failed",
                job_id=str(job_id),
                status=status,
                error=str(e)
            )
            raise ValueError(f"Failed to update resume job status: {str(e)}")
    
    def mark_job_processing(
        self,
        db: Session,
        job_id: UUID
    ) -> bool:
        """Mark a resume job as processing.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            
        Returns:
            True if marked successfully, False if not found
        """
        return self.repository.mark_processing(db, job_id)
    
    def mark_job_completed(
        self,
        db: Session,
        job_id: UUID
    ) -> bool:
        """Mark a resume job as completed.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            
        Returns:
            True if marked successfully, False if not found
        """
        return self.repository.mark_completed(db, job_id)
    
    def mark_job_failed(
        self,
        db: Session,
        job_id: UUID,
        error_message: str
    ) -> bool:
        """Mark a resume job as failed with error message.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            error_message: Error message describing the failure
            
        Returns:
            True if marked successfully, False if not found
        """
        return self.repository.mark_failed(db, job_id, error_message)
    
    def retry_failed_job(
        self,
        db: Session,
        job_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Reset a failed job to pending for retry with audit logging.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if reset successfully, False if not found or not failed
        """
        try:
            success = self.repository.retry_failed_job(db, job_id)
            
            if success:
                logger.info(
                    "Resume job retry initiated",
                    job_id=str(job_id),
                    user_id=str(user_id) if user_id else None
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Resume job retry failed",
                job_id=str(job_id),
                error=str(e)
            )
            return False
    
    def get_jobs_by_file_name(
        self,
        db: Session,
        client_id: UUID,
        file_name: str
    ) -> List[ResumeJob]:
        """Get resume jobs by file name within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            file_name: Resume file name
            
        Returns:
            List of resume jobs with specified file name
        """
        return self.repository.get_jobs_by_file_name(db, client_id, file_name)
    
    def get_processing_statistics(
        self,
        db: Session,
        client_id: UUID
    ) -> Dict[str, Any]:
        """Get processing statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with processing statistics
        """
        return self.repository.get_processing_stats(db, client_id)
    
    def count_jobs_by_status(
        self,
        db: Session,
        client_id: UUID,
        status: str
    ) -> int:
        """Count resume jobs by status within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            status: Job status
            
        Returns:
            Number of jobs with specified status
        """
        return self.repository.count_by_status(db, client_id, status)
    
    def get_client_jobs(
        self,
        db: Session,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[ResumeJob]:
        """Get all resume jobs for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of resume jobs for the client
        """
        return self.repository.get_multi(
            db, skip, limit, {"client_id": client_id}
        )
    
    def delete_job(
        self,
        db: Session,
        job_id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Delete a resume job with audit logging.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            client_id: Client UUID
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if deleted, False if not found
        """
        try:
            deleted = self.repository.delete_with_audit(
                db=db,
                id=job_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if deleted:
                logger.info(
                    "Resume job deleted",
                    job_id=str(job_id),
                    client_id=str(client_id)
                )
            
            return deleted
            
        except Exception as e:
            logger.error(
                "Resume job deletion failed",
                job_id=str(job_id),
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to delete resume job: {str(e)}")
    
    def process_next_job(
        self,
        db: Session,
        processor_callback: callable
    ) -> Optional[ResumeJob]:
        """Process the next pending job using provided callback.
        
        Args:
            db: Database session
            processor_callback: Function to process the job
            
        Returns:
            Processed job if successful, None if no jobs available
        """
        # Get the next pending job
        pending_jobs = self.get_pending_jobs(db, limit=1)
        if not pending_jobs:
            return None
        
        job = pending_jobs[0]
        
        try:
            # Mark as processing
            self.mark_job_processing(db, job.id)
            
            # Process the job using callback
            processor_callback(job)
            
            # Mark as completed
            self.mark_job_completed(db, job.id)
            
            logger.info(
                "Resume job processed successfully",
                job_id=str(job.id),
                file_name=job.file_name
            )
            
            return job
            
        except Exception as e:
            # Mark as failed
            error_message = f"Processing failed: {str(e)}"
            self.mark_job_failed(db, job.id, error_message)
            
            logger.error(
                "Resume job processing failed",
                job_id=str(job.id),
                file_name=job.file_name,
                error=str(e)
            )
            
            return job