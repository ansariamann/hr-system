"""Celery tasks for resume processing."""

from typing import Dict, Any, Optional
from uuid import UUID
from celery import Task
import structlog
from pathlib import Path

from ats_backend.workers.celery_app import celery_app
from ats_backend.core.database import get_db
from ats_backend.resume.parser import ResumeParser
from ats_backend.services.resume_job_service import ResumeJobService
from ats_backend.services.candidate_service import CandidateService
from ats_backend.services.application_service import ApplicationService
from ats_backend.schemas.candidate import CandidateCreate
from ats_backend.schemas.application import ApplicationCreate

logger = structlog.get_logger(__name__)


class ResumeProcessingTask(Task):
    """Base task class for resume processing with error handling."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 120}  # Longer countdown for resume processing
    retry_backoff = True
    retry_jitter = True


@celery_app.task(bind=True, base=ResumeProcessingTask, name="process_resume_file")
def process_resume_file(
    self,
    client_id: str,
    job_id: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process a resume file asynchronously.
    
    Args:
        client_id: Client UUID string
        job_id: Resume job UUID string
        user_id: User UUID string (optional)
        
    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(
            "Starting resume processing task",
            task_id=self.request.id,
            client_id=client_id,
            job_id=job_id
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get services
            resume_job_service = ResumeJobService()
            candidate_service = CandidateService()
            application_service = ApplicationService()
            
            # Get the resume job
            job = resume_job_service.get_job(db, UUID(job_id))
            if not job:
                raise ValueError(f"Resume job not found: {job_id}")
            
            if job.status != "PENDING":
                logger.warning(
                    "Resume job is not in PENDING status",
                    job_id=job_id,
                    current_status=job.status
                )
                return {
                    "success": False,
                    "message": f"Job is not in PENDING status: {job.status}",
                    "job_id": job_id,
                    "task_id": self.request.id
                }
            
            # Update job status to PROCESSING
            resume_job_service.update_job_status(
                db, UUID(job_id), "PROCESSING", user_id=UUID(user_id) if user_id else None
            )
            
            # Initialize resume parser
            parser = ResumeParser()
            
            # Parse the resume file
            file_path = Path(job.file_path)
            parsing_result = parser.parse_file(file_path)
            
            if not parsing_result.success:
                # Update job with error
                resume_job_service.update_job_status(
                    db, UUID(job_id), "FAILED", 
                    error_message=parsing_result.error_message,
                    user_id=UUID(user_id) if user_id else None
                )
                
                logger.error(
                    "Resume parsing failed",
                    task_id=self.request.id,
                    job_id=job_id,
                    error=parsing_result.error_message
                )
                
                return {
                    "success": False,
                    "message": f"Resume parsing failed: {parsing_result.error_message}",
                    "job_id": job_id,
                    "task_id": self.request.id
                }
            
            # Convert parsed resume to candidate data
            parsed_resume = parsing_result.parsed_resume
            candidate_data = parsed_resume.to_candidate_data()
            
            # Use duplicate detection service for comprehensive analysis
            from ats_backend.services.duplicate_detection_service import DuplicateDetectionService
            duplicate_service = DuplicateDetectionService()
            
            hash_data = parsed_resume.get_candidate_hash_data()
            
            # Perform duplicate detection analysis
            duplicate_result = duplicate_service.detect_duplicates(
                db=db,
                client_id=UUID(client_id),
                candidate_data=hash_data
            )
            
            # Extract flagging information
            flagged_for_review = duplicate_result.should_flag
            flag_reason = duplicate_result.flag_reason
            
            if duplicate_result.has_duplicates:
                logger.info(
                    "Duplicate candidates detected",
                    job_id=job_id,
                    matches_count=len(duplicate_result.matches),
                    should_flag=flagged_for_review,
                    similarity_scores=[match.similarity_score for match in duplicate_result.matches]
                )
                
                # Log details of matches for debugging
                for match in duplicate_result.matches:
                    logger.debug(
                        "Duplicate match details",
                        job_id=job_id,
                        match_candidate_id=str(match.candidate.id),
                        match_type=match.match_type,
                        similarity_score=match.similarity_score,
                        matching_fields=match.matching_fields,
                        candidate_status=match.candidate.status
                    )
            
            # Add candidate hash to data
            candidate_data["candidate_hash"] = duplicate_result.candidate_hash
            
            # Create candidate
            candidate_create = CandidateCreate(**candidate_data)
            candidate = candidate_service.create_candidate(
                db=db,
                client_id=UUID(client_id),
                candidate_data=candidate_create,
                user_id=UUID(user_id) if user_id else None
            )
            
            # Create application linking the candidate to this resume job
            application_create = ApplicationCreate(
                candidate_id=candidate.id,
                job_title="Resume Submission",  # Default job title
                status="RECEIVED",
                flagged_for_review=flagged_for_review,
                flag_reason=flag_reason
            )
            
            application = application_service.create_application(
                db=db,
                client_id=UUID(client_id),
                application_data=application_create,
                user_id=UUID(user_id) if user_id else None
            )
            
            # Update job status to COMPLETED
            resume_job_service.update_job_status(
                db, UUID(job_id), "COMPLETED",
                user_id=UUID(user_id) if user_id else None
            )
            
            logger.info(
                "Resume processing task completed successfully",
                task_id=self.request.id,
                job_id=job_id,
                candidate_id=str(candidate.id),
                application_id=str(application.id),
                parsing_method=parsed_resume.parsing_method,
                confidence_score=parsed_resume.confidence_score
            )
            
            return {
                "success": True,
                "message": "Resume processed successfully",
                "job_id": job_id,
                "candidate_id": str(candidate.id),
                "application_id": str(application.id),
                "parsing_method": parsed_resume.parsing_method,
                "confidence_score": parsed_resume.confidence_score,
                "extracted_fields": {
                    "name": parsed_resume.contact_info.name,
                    "email": parsed_resume.contact_info.email,
                    "phone": parsed_resume.contact_info.phone,
                    "skills_count": len(parsed_resume.skills),
                    "experience_count": len(parsed_resume.experience),
                    "education_count": len(parsed_resume.education)
                },
                "task_id": self.request.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Resume processing task failed",
            task_id=self.request.id,
            client_id=client_id,
            job_id=job_id,
            error=str(e),
            retry_count=self.request.retries
        )
        
        # Try to update job status to failed if possible
        try:
            db = next(get_db())
            try:
                resume_job_service = ResumeJobService()
                resume_job_service.update_job_status(
                    db, UUID(job_id), "FAILED",
                    error_message=str(e),
                    user_id=UUID(user_id) if user_id else None
                )
            finally:
                db.close()
        except:
            pass  # Don't fail the retry if we can't update status
        
        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e)


@celery_app.task(bind=True, name="batch_process_resumes")
def batch_process_resumes(
    self,
    client_id: str,
    job_ids: list[str],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process multiple resume files in batch.
    
    Args:
        client_id: Client UUID string
        job_ids: List of resume job UUID strings
        user_id: User UUID string (optional)
        
    Returns:
        Dictionary with batch processing results
    """
    try:
        logger.info(
            "Starting batch resume processing task",
            task_id=self.request.id,
            client_id=client_id,
            job_count=len(job_ids)
        )
        
        results = []
        successful_count = 0
        failed_count = 0
        
        for job_id in job_ids:
            try:
                # Process each resume individually
                result = process_resume_file.apply(
                    args=[client_id, job_id, user_id]
                )
                
                if result.successful():
                    task_result = result.get()
                    if task_result.get("success", False):
                        successful_count += 1
                    else:
                        failed_count += 1
                    results.append(task_result)
                else:
                    failed_count += 1
                    results.append({
                        "success": False,
                        "job_id": job_id,
                        "message": "Task execution failed"
                    })
                    
            except Exception as e:
                failed_count += 1
                results.append({
                    "success": False,
                    "job_id": job_id,
                    "message": f"Processing failed: {str(e)}"
                })
                
                logger.error(
                    "Individual resume processing failed in batch",
                    job_id=job_id,
                    error=str(e)
                )
        
        logger.info(
            "Batch resume processing task completed",
            task_id=self.request.id,
            client_id=client_id,
            total_jobs=len(job_ids),
            successful=successful_count,
            failed=failed_count
        )
        
        return {
            "success": True,
            "message": f"Batch processing completed: {successful_count} successful, {failed_count} failed",
            "total_jobs": len(job_ids),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "results": results,
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(
            "Batch resume processing task failed",
            task_id=self.request.id,
            client_id=client_id,
            error=str(e)
        )
        
        return {
            "success": False,
            "message": f"Batch processing failed: {str(e)}",
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="reprocess_failed_resume")
def reprocess_failed_resume(
    self,
    client_id: str,
    job_id: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Reprocess a failed resume job.
    
    Args:
        client_id: Client UUID string
        job_id: Resume job UUID string
        user_id: User UUID string (optional)
        
    Returns:
        Dictionary with reprocessing results
    """
    try:
        logger.info(
            "Starting resume reprocessing task",
            task_id=self.request.id,
            client_id=client_id,
            job_id=job_id
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            resume_job_service = ResumeJobService()
            
            # Get the resume job
            job = resume_job_service.get_job(db, UUID(job_id))
            if not job:
                raise ValueError(f"Resume job not found: {job_id}")
            
            if job.status != "FAILED":
                logger.warning(
                    "Resume job is not in FAILED status",
                    job_id=job_id,
                    current_status=job.status
                )
                return {
                    "success": False,
                    "message": f"Job is not in FAILED status: {job.status}",
                    "job_id": job_id,
                    "task_id": self.request.id
                }
            
            # Reset job status to PENDING for reprocessing
            resume_job_service.update_job_status(
                db, UUID(job_id), "PENDING",
                error_message=None,  # Clear previous error
                user_id=UUID(user_id) if user_id else None
            )
            
        finally:
            db.close()
        
        # Process the resume using the main processing task
        result = process_resume_file.apply(
            args=[client_id, job_id, user_id]
        )
        
        if result.successful():
            task_result = result.get()
            
            logger.info(
                "Resume reprocessing task completed",
                task_id=self.request.id,
                job_id=job_id,
                success=task_result.get("success", False)
            )
            
            return task_result
        else:
            logger.error(
                "Resume reprocessing task failed",
                task_id=self.request.id,
                job_id=job_id
            )
            
            return {
                "success": False,
                "message": "Reprocessing task execution failed",
                "job_id": job_id,
                "task_id": self.request.id
            }
            
    except Exception as e:
        logger.error(
            "Resume reprocessing task failed",
            task_id=self.request.id,
            client_id=client_id,
            job_id=job_id,
            error=str(e)
        )
        
        return {
            "success": False,
            "message": f"Reprocessing failed: {str(e)}",
            "job_id": job_id,
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="validate_resume_parsing")
def validate_resume_parsing(
    self,
    file_path: str,
    expected_fields: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate resume parsing functionality (for testing/debugging).
    
    Args:
        file_path: Path to resume file to test
        expected_fields: Expected fields for validation (optional)
        
    Returns:
        Dictionary with validation results
    """
    try:
        logger.info(
            "Starting resume parsing validation task",
            task_id=self.request.id,
            file_path=file_path
        )
        
        # Initialize resume parser
        parser = ResumeParser()
        
        # Parse the resume file
        parsing_result = parser.parse_file(Path(file_path))
        
        if not parsing_result.success:
            return {
                "success": False,
                "message": f"Parsing failed: {parsing_result.error_message}",
                "file_path": file_path,
                "task_id": self.request.id
            }
        
        parsed_resume = parsing_result.parsed_resume
        
        # Extract validation data
        validation_data = {
            "parsing_method": parsed_resume.parsing_method,
            "confidence_score": parsed_resume.confidence_score,
            "raw_text_length": len(parsed_resume.raw_text),
            "contact_info": {
                "name": parsed_resume.contact_info.name,
                "email": parsed_resume.contact_info.email,
                "phone": parsed_resume.contact_info.phone
            },
            "skills_count": len(parsed_resume.skills),
            "experience_count": len(parsed_resume.experience),
            "education_count": len(parsed_resume.education),
            "has_salary_info": parsed_resume.salary_info is not None
        }
        
        # Validate against expected fields if provided
        validation_errors = []
        if expected_fields:
            for field, expected_value in expected_fields.items():
                actual_value = validation_data.get(field)
                if actual_value != expected_value:
                    validation_errors.append(
                        f"Field '{field}': expected {expected_value}, got {actual_value}"
                    )
        
        logger.info(
            "Resume parsing validation task completed",
            task_id=self.request.id,
            file_path=file_path,
            validation_errors_count=len(validation_errors)
        )
        
        return {
            "success": True,
            "message": "Parsing validation completed",
            "file_path": file_path,
            "validation_data": validation_data,
            "validation_errors": validation_errors,
            "is_valid": len(validation_errors) == 0,
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(
            "Resume parsing validation task failed",
            task_id=self.request.id,
            file_path=file_path,
            error=str(e)
        )
        
        return {
            "success": False,
            "message": f"Validation failed: {str(e)}",
            "file_path": file_path,
            "task_id": self.request.id
        }