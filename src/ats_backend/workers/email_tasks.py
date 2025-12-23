"""Celery tasks for email processing."""

from typing import Dict, Any, Optional
from uuid import UUID
from celery import Task
import structlog

from ats_backend.workers.celery_app import celery_app
from ats_backend.core.database import get_db
from ats_backend.email.processor import EmailProcessor
from ats_backend.email.models import EmailMessage, EmailIngestionResponse

logger = structlog.get_logger(__name__)


class EmailProcessingTask(Task):
    """Base task class for email processing with error handling."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    retry_jitter = True


@celery_app.task(bind=True, base=EmailProcessingTask, name="process_email_message")
def process_email_message(
    self,
    client_id: str,
    email_data: Dict[str, Any],
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """Process an email message asynchronously.
    
    Args:
        client_id: Client UUID string
        email_data: Email message data dictionary
        user_id: User UUID string (optional)
        ip_address: IP address of the request (optional)
        user_agent: User agent of the request (optional)
        
    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(
            "Starting email processing task",
            task_id=self.request.id,
            client_id=client_id,
            message_id=email_data.get("message_id")
        )
        
        # Parse email data
        email = EmailMessage(**email_data)
        
        # Get database session
        db = next(get_db())
        
        try:
            # Process email
            processor = EmailProcessor()
            result = processor.process_email(
                db=db,
                client_id=UUID(client_id),
                email=email,
                user_id=UUID(user_id) if user_id else None,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(
                "Email processing task completed",
                task_id=self.request.id,
                client_id=client_id,
                message_id=email.message_id,
                success=result.success,
                jobs_created=len(result.job_ids)
            )
            
            return {
                "success": result.success,
                "message": result.message,
                "job_ids": [str(job_id) for job_id in result.job_ids],
                "processed_attachments": result.processed_attachments,
                "duplicate_message_id": result.duplicate_message_id,
                "task_id": self.request.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Email processing task failed",
            task_id=self.request.id,
            client_id=client_id,
            message_id=email_data.get("message_id"),
            error=str(e),
            retry_count=self.request.retries
        )
        
        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e)


@celery_app.task(bind=True, name="cleanup_old_files")
def cleanup_old_files(self, days_old: int = 30) -> Dict[str, Any]:
    """Clean up old files from storage.
    
    Args:
        days_old: Number of days after which files should be cleaned up
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(
            "Starting file cleanup task",
            task_id=self.request.id,
            days_old=days_old
        )
        
        from ats_backend.email.storage import FileStorageService
        
        storage_service = FileStorageService()
        files_cleaned = storage_service.cleanup_old_files(days_old)
        
        logger.info(
            "File cleanup task completed",
            task_id=self.request.id,
            files_cleaned=files_cleaned,
            days_old=days_old
        )
        
        return {
            "success": True,
            "files_cleaned": files_cleaned,
            "days_old": days_old,
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(
            "File cleanup task failed",
            task_id=self.request.id,
            days_old=days_old,
            error=str(e)
        )
        
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="cleanup_failed_jobs")
def cleanup_failed_jobs(
    self,
    client_id: str,
    max_age_hours: int = 24
) -> Dict[str, Any]:
    """Clean up old failed jobs for a client.
    
    Args:
        client_id: Client UUID string
        max_age_hours: Maximum age in hours for failed jobs to keep
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(
            "Starting failed jobs cleanup task",
            task_id=self.request.id,
            client_id=client_id,
            max_age_hours=max_age_hours
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            processor = EmailProcessor()
            jobs_cleaned = processor.cleanup_failed_jobs(
                db, UUID(client_id), max_age_hours
            )
            
            logger.info(
                "Failed jobs cleanup task completed",
                task_id=self.request.id,
                client_id=client_id,
                jobs_cleaned=jobs_cleaned
            )
            
            return {
                "success": True,
                "jobs_cleaned": jobs_cleaned,
                "client_id": client_id,
                "max_age_hours": max_age_hours,
                "task_id": self.request.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Failed jobs cleanup task failed",
            task_id=self.request.id,
            client_id=client_id,
            error=str(e)
        )
        
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="validate_email_format")
def validate_email_format(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate email message format asynchronously.
    
    Args:
        email_data: Email message data dictionary
        
    Returns:
        Dictionary with validation results
    """
    try:
        logger.info(
            "Starting email validation task",
            task_id=self.request.id,
            message_id=email_data.get("message_id")
        )
        
        # Parse and validate email
        email = EmailMessage(**email_data)
        
        processor = EmailProcessor()
        validation_errors = processor.validate_email_message(email)
        
        is_valid = len(validation_errors) == 0
        
        logger.info(
            "Email validation task completed",
            task_id=self.request.id,
            message_id=email.message_id,
            is_valid=is_valid,
            error_count=len(validation_errors)
        )
        
        return {
            "valid": is_valid,
            "errors": validation_errors,
            "message_id": email.message_id,
            "attachment_count": len(email.attachments),
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(
            "Email validation task failed",
            task_id=self.request.id,
            message_id=email_data.get("message_id"),
            error=str(e)
        )
        
        return {
            "valid": False,
            "errors": [f"Validation failed: {str(e)}"],
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="cleanup_failed_jobs_all_clients")
def cleanup_failed_jobs_all_clients(
    self,
    max_age_hours: int = 24
) -> Dict[str, Any]:
    """Clean up old failed jobs for all clients (periodic task).
    
    Args:
        max_age_hours: Maximum age in hours for failed jobs to keep
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(
            "Starting global failed jobs cleanup task",
            task_id=self.request.id,
            max_age_hours=max_age_hours
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            from ats_backend.services.client_service import ClientService
            
            client_service = ClientService()
            processor = EmailProcessor()
            
            # Get all clients
            clients = client_service.get_all_clients(db)
            
            total_jobs_cleaned = 0
            clients_processed = 0
            
            for client in clients:
                try:
                    jobs_cleaned = processor.cleanup_failed_jobs(
                        db, client.id, max_age_hours
                    )
                    total_jobs_cleaned += jobs_cleaned
                    clients_processed += 1
                    
                    logger.debug(
                        "Cleaned failed jobs for client",
                        client_id=str(client.id),
                        jobs_cleaned=jobs_cleaned
                    )
                    
                except Exception as e:
                    logger.error(
                        "Failed to clean jobs for client",
                        client_id=str(client.id),
                        error=str(e)
                    )
            
            logger.info(
                "Global failed jobs cleanup task completed",
                task_id=self.request.id,
                clients_processed=clients_processed,
                total_jobs_cleaned=total_jobs_cleaned
            )
            
            return {
                "success": True,
                "clients_processed": clients_processed,
                "total_jobs_cleaned": total_jobs_cleaned,
                "max_age_hours": max_age_hours,
                "task_id": self.request.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Global failed jobs cleanup task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="get_processing_stats")
def get_processing_stats(
    self,
    client_id: str,
    days_back: int = 30
) -> Dict[str, Any]:
    """Get processing statistics for a client asynchronously.
    
    Args:
        client_id: Client UUID string
        days_back: Number of days to look back for statistics
        
    Returns:
        Dictionary with processing statistics
    """
    try:
        logger.info(
            "Starting processing stats task",
            task_id=self.request.id,
            client_id=client_id,
            days_back=days_back
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            processor = EmailProcessor()
            stats = processor.get_processing_statistics(
                db, UUID(client_id), days_back
            )
            
            logger.info(
                "Processing stats task completed",
                task_id=self.request.id,
                client_id=client_id
            )
            
            stats["task_id"] = self.request.id
            return stats
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Processing stats task failed",
            task_id=self.request.id,
            client_id=client_id,
            error=str(e)
        )
        
        return {
            "error": str(e),
            "client_id": client_id,
            "task_id": self.request.id
        }