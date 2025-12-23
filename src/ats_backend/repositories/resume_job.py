"""Resume job repository for database operations."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_
import structlog

from ats_backend.models.resume_job import ResumeJob
from .audited_base import AuditedRepository

logger = structlog.get_logger(__name__)


class ResumeJobRepository(AuditedRepository[ResumeJob]):
    """Repository for ResumeJob model operations."""
    
    def __init__(self):
        super().__init__(ResumeJob)
    
    def get_by_email_message_id(self, db: Session, email_message_id: str) -> Optional[ResumeJob]:
        """Get resume job by email message ID for deduplication.
        
        Args:
            db: Database session
            email_message_id: Email message ID
            
        Returns:
            ResumeJob if found, None otherwise
        """
        return db.query(ResumeJob).filter(
            ResumeJob.email_message_id == email_message_id
        ).first()
    
    def get_by_status(
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
        return (
            db.query(ResumeJob)
            .filter(
                and_(
                    ResumeJob.client_id == client_id,
                    ResumeJob.status == status
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_pending_jobs(self, db: Session, limit: int = 100) -> List[ResumeJob]:
        """Get pending resume jobs across all clients.
        
        Args:
            db: Database session
            limit: Maximum number of jobs to return
            
        Returns:
            List of pending resume jobs
        """
        return (
            db.query(ResumeJob)
            .filter(ResumeJob.status == "PENDING")
            .order_by(ResumeJob.created_at)
            .limit(limit)
            .all()
        )
    
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
        return (
            db.query(ResumeJob)
            .filter(
                and_(
                    ResumeJob.client_id == client_id,
                    ResumeJob.status == "FAILED"
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def mark_processing(self, db: Session, job_id: UUID) -> bool:
        """Mark a resume job as processing.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            
        Returns:
            True if marked successfully, False if not found
        """
        job = self.get_by_id(db, job_id)
        if not job:
            logger.warning("Resume job not found for processing", job_id=str(job_id))
            return False
        
        job.status = "PROCESSING"
        db.commit()
        
        logger.info("Resume job marked as processing", job_id=str(job_id))
        return True
    
    def mark_completed(self, db: Session, job_id: UUID) -> bool:
        """Mark a resume job as completed.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            
        Returns:
            True if marked successfully, False if not found
        """
        job = self.get_by_id(db, job_id)
        if not job:
            logger.warning("Resume job not found for completion", job_id=str(job_id))
            return False
        
        job.mark_processed()
        db.commit()
        
        logger.info("Resume job marked as completed", job_id=str(job_id))
        return True
    
    def mark_failed(self, db: Session, job_id: UUID, error_message: str) -> bool:
        """Mark a resume job as failed with error message.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            error_message: Error message describing the failure
            
        Returns:
            True if marked successfully, False if not found
        """
        job = self.get_by_id(db, job_id)
        if not job:
            logger.warning("Resume job not found for failure", job_id=str(job_id))
            return False
        
        job.mark_failed(error_message)
        db.commit()
        
        logger.info(
            "Resume job marked as failed",
            job_id=str(job_id),
            error_message=error_message
        )
        return True
    
    def retry_failed_job(self, db: Session, job_id: UUID) -> bool:
        """Reset a failed job to pending for retry.
        
        Args:
            db: Database session
            job_id: Resume job UUID
            
        Returns:
            True if reset successfully, False if not found or not failed
        """
        job = self.get_by_id(db, job_id)
        if not job:
            logger.warning("Resume job not found for retry", job_id=str(job_id))
            return False
        
        if job.status != "FAILED":
            logger.warning("Resume job is not in failed state", job_id=str(job_id), status=job.status)
            return False
        
        job.status = "PENDING"
        job.error_message = None
        job.processed_at = None
        db.commit()
        
        logger.info("Resume job reset for retry", job_id=str(job_id))
        return True
    
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
        return (
            db.query(ResumeJob)
            .filter(
                and_(
                    ResumeJob.client_id == client_id,
                    ResumeJob.file_name == file_name
                )
            )
            .all()
        )
    
    def count_by_status(self, db: Session, client_id: UUID, status: str) -> int:
        """Count resume jobs by status within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            status: Job status
            
        Returns:
            Number of jobs with specified status
        """
        return (
            db.query(ResumeJob)
            .filter(
                and_(
                    ResumeJob.client_id == client_id,
                    ResumeJob.status == status
                )
            )
            .count()
        )
    
    def get_processing_stats(self, db: Session, client_id: UUID) -> dict:
        """Get processing statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            "total_jobs": self.count(db, {"client_id": client_id}),
            "pending_jobs": self.count_by_status(db, client_id, "PENDING"),
            "processing_jobs": self.count_by_status(db, client_id, "PROCESSING"),
            "completed_jobs": self.count_by_status(db, client_id, "COMPLETED"),
            "failed_jobs": self.count_by_status(db, client_id, "FAILED"),
        }
        
        logger.debug("Processing stats retrieved", client_id=str(client_id), stats=stats)
        return stats