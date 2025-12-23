"""Email ingestion API endpoints."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.email.models import (
    EmailIngestionRequest,
    EmailIngestionResponse,
    EmailMessage,
    EmailProcessingStats
)
from ats_backend.email.processor import EmailProcessor
from ats_backend.email.parser import EmailParser
from ats_backend.workers.email_tasks import (
    process_email_message,
    cleanup_old_files,
    cleanup_failed_jobs,
    validate_email_format,
    get_processing_stats
)
from ats_backend.services.resume_job_service import ResumeJobService
from ats_backend.schemas.resume_job import ResumeJobResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/ingest", response_model=EmailIngestionResponse)
async def ingest_email(
    request: Request,
    background_tasks: BackgroundTasks,
    email_request: EmailIngestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Ingest email with resume attachments for processing.
    
    This endpoint receives emails with resume attachments and creates
    background jobs for processing. Supports deduplication and multiple
    file formats (PDF, PNG, JPG, TIFF).
    """
    try:
        # Validate client ID matches current user's client
        if email_request.client_id != current_client.id:
            logger.warning(
                "Client ID mismatch in email ingestion",
                request_client_id=str(email_request.client_id),
                user_client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client ID does not match authenticated user's client"
            )
        
        # Get request metadata
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        logger.info(
            "Email ingestion request received",
            message_id=email_request.email.message_id,
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            attachment_count=len(email_request.email.attachments)
        )
        
        # Validate email message
        processor = EmailProcessor()
        validation_errors = processor.validate_email_message(email_request.email)
        
        if validation_errors:
            logger.warning(
                "Email validation failed",
                message_id=email_request.email.message_id,
                errors=validation_errors
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email validation failed: {'; '.join(validation_errors)}"
            )
        
        # Process email synchronously for immediate response
        # For high-volume scenarios, this could be made async
        result = processor.process_email(
            db=db,
            client_id=current_client.id,
            email=email_request.email,
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Schedule background cleanup tasks
        background_tasks.add_task(
            cleanup_old_files.delay,
            days_old=30
        )
        
        logger.info(
            "Email ingestion completed",
            message_id=email_request.email.message_id,
            client_id=str(current_client.id),
            success=result.success,
            jobs_created=len(result.job_ids)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Email ingestion failed",
            message_id=email_request.email.message_id if email_request.email else "unknown",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email ingestion failed: {str(e)}"
        )


@router.post("/ingest/async", response_model=Dict[str, Any])
async def ingest_email_async(
    request: Request,
    email_request: EmailIngestionRequest,
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Ingest email asynchronously using Celery task queue.
    
    This endpoint queues email processing as a background task and
    returns immediately with a task ID for status tracking.
    """
    try:
        # Validate client ID matches current user's client
        if email_request.client_id != current_client.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client ID does not match authenticated user's client"
            )
        
        # Get request metadata
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        logger.info(
            "Async email ingestion request received",
            message_id=email_request.email.message_id,
            client_id=str(current_client.id),
            user_id=str(current_user.id)
        )
        
        # Queue email processing task
        task = process_email_message.delay(
            client_id=str(current_client.id),
            email_data=email_request.email.dict(),
            user_id=str(current_user.id),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "success": True,
            "message": "Email queued for processing",
            "task_id": task.id,
            "message_id": email_request.email.message_id,
            "status_url": f"/email/task/{task.id}/status"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Async email ingestion failed",
            message_id=email_request.email.message_id,
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Async email ingestion failed: {str(e)}"
        )


@router.get("/task/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of an email processing task."""
    try:
        from ats_backend.workers.celery_app import celery_app
        
        task_result = celery_app.AsyncResult(task_id)
        
        if task_result.state == "PENDING":
            response = {
                "task_id": task_id,
                "state": task_result.state,
                "status": "Task is waiting to be processed"
            }
        elif task_result.state == "PROGRESS":
            response = {
                "task_id": task_id,
                "state": task_result.state,
                "status": "Task is being processed",
                "progress": task_result.info
            }
        elif task_result.state == "SUCCESS":
            response = {
                "task_id": task_id,
                "state": task_result.state,
                "status": "Task completed successfully",
                "result": task_result.result
            }
        else:  # FAILURE
            response = {
                "task_id": task_id,
                "state": task_result.state,
                "status": "Task failed",
                "error": str(task_result.info)
            }
        
        return response
        
    except Exception as e:
        logger.error("Failed to get task status", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.get("/jobs", response_model=List[ResumeJobResponse])
async def get_resume_jobs(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get resume jobs for the current client."""
    try:
        resume_job_service = ResumeJobService()
        
        if status:
            jobs = resume_job_service.get_jobs_by_status(
                db, current_client.id, status, skip, limit
            )
        else:
            jobs = resume_job_service.get_client_jobs(
                db, current_client.id, skip, limit
            )
        
        return jobs
        
    except Exception as e:
        logger.error(
            "Failed to get resume jobs",
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resume jobs: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=ResumeJobResponse)
async def get_resume_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get a specific resume job by ID."""
    try:
        resume_job_service = ResumeJobService()
        job = resume_job_service.get_job_by_id(db, job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume job not found"
            )
        
        # Verify job belongs to current client
        if job.client_id != current_client.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this resume job"
            )
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get resume job",
            job_id=str(job_id),
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resume job: {str(e)}"
        )


@router.post("/jobs/{job_id}/retry")
async def retry_failed_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Retry a failed resume job."""
    try:
        processor = EmailProcessor()
        success = processor.retry_failed_processing(
            db, current_client.id, job_id, current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retry job (job not found or not in failed state)"
            )
        
        return {
            "success": True,
            "message": "Job retry initiated successfully",
            "job_id": str(job_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retry job",
            job_id=str(job_id),
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry job: {str(e)}"
        )


@router.get("/stats")
async def get_processing_statistics(
    days_back: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get email processing statistics for the current client."""
    try:
        processor = EmailProcessor()
        stats = processor.get_processing_statistics(
            db, current_client.id, days_back
        )
        
        return stats
        
    except Exception as e:
        logger.error(
            "Failed to get processing statistics",
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get processing statistics: {str(e)}"
        )


@router.post("/cleanup/failed-jobs")
async def cleanup_failed_jobs_endpoint(
    max_age_hours: int = 24,
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Clean up old failed jobs for the current client."""
    try:
        # Queue cleanup task
        task = cleanup_failed_jobs.delay(
            client_id=str(current_client.id),
            max_age_hours=max_age_hours
        )
        
        return {
            "success": True,
            "message": "Cleanup task queued",
            "task_id": task.id,
            "max_age_hours": max_age_hours
        }
        
    except Exception as e:
        logger.error(
            "Failed to queue cleanup task",
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue cleanup task: {str(e)}"
        )


@router.post("/webhook/raw")
async def email_webhook_raw(
    request: Request,
    background_tasks: BackgroundTasks,
    raw_email: str,
    client_id: UUID,
    db: Session = Depends(get_db)
):
    """Webhook endpoint for receiving raw email data.
    
    This endpoint can be used by email services to send raw email data
    directly to the ATS system for processing. Authentication is handled
    via API key or other webhook-specific authentication.
    """
    try:
        logger.info(
            "Raw email webhook received",
            client_id=str(client_id),
            content_length=len(raw_email)
        )
        
        # Parse raw email
        parser = EmailParser()
        email_message = parser.parse_raw_email(raw_email)
        
        # Get request metadata
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Process email
        processor = EmailProcessor()
        result = processor.process_email(
            db=db,
            client_id=client_id,
            email=email_message,
            user_id=None,  # No user for webhook
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Schedule background cleanup
        background_tasks.add_task(
            cleanup_old_files.delay,
            days_old=30
        )
        
        logger.info(
            "Raw email webhook processed",
            message_id=email_message.message_id,
            client_id=str(client_id),
            success=result.success
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Raw email webhook failed",
            client_id=str(client_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email webhook processing failed: {str(e)}"
        )


@router.post("/validate")
async def validate_email_message(
    email: EmailMessage,
    current_user: User = Depends(get_current_user)
):
    """Validate email message format without processing."""
    try:
        # Queue validation task
        task = validate_email_format.delay(email.dict())
        
        return {
            "success": True,
            "message": "Validation task queued",
            "task_id": task.id,
            "message_id": email.message_id
        }
        
    except Exception as e:
        logger.error(
            "Failed to queue validation task",
            message_id=email.message_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue validation task: {str(e)}"
        )