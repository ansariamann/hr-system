"""Application management service."""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.application import Application
from ats_backend.models.client import Client
from ats_backend.models.job import Job
from ats_backend.models.interview_record import InterviewRecord
from ats_backend.core.session_context import with_client_context
from ats_backend.repositories.application import ApplicationRepository
from ats_backend.repositories.candidate import CandidateRepository
from ats_backend.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    normalize_application_status,
)
from ats_backend.core.event_publisher import event_publisher

logger = structlog.get_logger(__name__)


class ApplicationService:
    """Service for managing application operations."""
    
    def __init__(self):
        self.repository = ApplicationRepository()

    @staticmethod
    def _build_prior_rejection_remark(previous_applications: List[Application]) -> Optional[str]:
        rejected_titles: List[str] = []
        for previous_application in previous_applications:
            if previous_application.status not in {"REJECTED", "WITHDRAWN"}:
                continue
            if not previous_application.job_title:
                continue
            if previous_application.job_title in rejected_titles:
                continue
            rejected_titles.append(previous_application.job_title)

        if not rejected_titles:
            return None

        if len(rejected_titles) == 1:
            return f"Rejected earlier for {rejected_titles[0]}"

        return f"Rejected earlier for {', '.join(rejected_titles[:-1])}, and {rejected_titles[-1]}"

    @staticmethod
    def _update_candidate_for_resubmission(
        candidate,
        previous_applications: List[Application],
    ) -> None:
        prior_rejection_remark = ApplicationService._build_prior_rejection_remark(previous_applications)
        if prior_rejection_remark:
            candidate.remark = prior_rejection_remark

        if candidate.status in {"REJECTED", "INACTIVE"}:
            candidate.status = "ACTIVE"
            candidate.updated_at = datetime.utcnow()

    @staticmethod
    def _sync_job_vacancy(db: Session, job_id: Optional[UUID]) -> None:
        if job_id is None:
            return
        from ats_backend.services.job_service import JobService
        JobService.sync_job_vacancy(db, job_id)

    @staticmethod
    def _has_filled_application_for_job(
        db: Session,
        job_id: UUID,
        exclude_application_id: Optional[UUID] = None,
    ) -> bool:
        """Return True when a job already has a non-deleted filled application."""
        query = db.query(Application.id).filter(
            Application.job_id == job_id,
            Application.deleted_at.is_(None),
            Application.status.in_(["HIRED", "SELECTED"]),
        )
        if exclude_application_id is not None:
            query = query.filter(Application.id != exclude_application_id)
        return query.first() is not None
    
    def create_application(
        self,
        db: Session,
        client_id: UUID,
        application_data: ApplicationCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        requesting_client_id: Optional[UUID] = None
    ) -> Application:
        """Create a new application with audit logging and real-time events.
        
        Args:
            db: Database session
            client_id: Client UUID
            application_data: Application creation data
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created application
            
        Raises:
            ValueError: If application creation fails
        """
        try:
            candidate_repo = CandidateRepository()
            candidate = candidate_repo.get_by_id_for_client(
                db, application_data.candidate_id, client_id
            )
            if (
                not candidate
                and requesting_client_id
                and requesting_client_id != client_id
            ):
                with with_client_context(db, requesting_client_id):
                    candidate = candidate_repo.get_by_id_for_client(
                        db, application_data.candidate_id, requesting_client_id
                    )
            if not candidate:
                candidate = candidate_repo.get_by_id(db, application_data.candidate_id)
            if not candidate:
                raise ValueError("Candidate not found")

            allowed_existing_clients = {None, client_id}
            if requesting_client_id:
                allowed_existing_clients.add(requesting_client_id)

            if candidate.client_id not in allowed_existing_clients:
                raise ValueError("Candidate not found for the selected client")
            if candidate.status == "SELECTED":
                raise ValueError("Selected candidates cannot be used to create a new application")

            target_client = db.query(Client).filter(Client.id == client_id).first()
            if target_client is None:
                raise ValueError("Target client not found")

            if candidate.client_id != client_id:
                candidate.client_id = client_id
                candidate.updated_at = datetime.utcnow()
            candidate.selected_client_name = target_client.name

            previous_applications = (
                db.query(Application)
                .filter(
                    Application.client_id == client_id,
                    Application.candidate_id == application_data.candidate_id,
                )
                .order_by(Application.created_at.desc())
                .all()
            )
            self._update_candidate_for_resubmission(candidate, previous_applications)

            application_payload = application_data.dict(
                exclude={"client_id"}, exclude_none=True
            )
            if "status" in application_payload:
                application_payload["status"] = normalize_application_status(application_payload["status"])
            job_id = application_payload.get("job_id")
            if job_id is None:
                raise ValueError("A job must be selected from available client jobs")

            job = (
                db.query(Job)
                .filter(Job.id == job_id, Job.client_id == client_id)
                .first()
            )
            if not job:
                raise ValueError("Job not found for the selected client")
            if not job.vacant or self._has_filled_application_for_job(db, job_id):
                raise ValueError("Selected job is no longer vacant")
            application_payload["job_title"] = job.title

            if user_id and not application_payload.get("applied_by_user_id"):
                application_payload["applied_by_user_id"] = user_id

            application = self.repository.create_with_audit(
                db=db,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **application_payload
            )
            self._sync_job_vacancy(db, application.job_id)
            
            logger.info(
                "Application created",
                application_id=str(application.id),
                client_id=str(client_id),
                candidate_id=str(application.candidate_id),
                status=application.status
            )
            
            # Publish real-time event
            if user_id:
                try:
                    # Get candidate name for the event
                    candidate_name = "Unknown"
                    if hasattr(application, 'candidate') and application.candidate:
                        candidate_name = application.candidate.name
                    else:
                        # Fallback: query candidate separately
                        candidate_repo = CandidateRepository()
                        candidate = candidate_repo.get_by_id(db, application.candidate_id)
                        if candidate:
                            candidate_name = candidate.name
                    
                    # Publish event asynchronously
                    asyncio.create_task(
                        event_publisher.publish_application_created(
                            tenant_id=client_id,
                            application_id=application.id,
                            candidate_id=application.candidate_id,
                            candidate_name=candidate_name,
                            status=application.status,
                            user_id=user_id,
                            additional_data={
                                "ip_address": ip_address,
                                "user_agent": user_agent
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to publish application created event",
                        application_id=str(application.id),
                        error=str(e)
                    )
            
            return application
            
        except Exception as e:
            logger.error(
                "Application creation failed",
                client_id=str(client_id),
                candidate_id=str(application_data.candidate_id),
                error=str(e)
            )
            raise ValueError(f"Failed to create application: {str(e)}")
    
    def get_application_by_id(
        self, 
        db: Session, 
        application_id: UUID
    ) -> Optional[Application]:
        """Get application by ID.
        
        Args:
            db: Database session
            application_id: Application UUID
            
        Returns:
            Application if found, None otherwise
        """
        return self.repository.get_by_id(db, application_id)
    
    def get_applications_by_candidate(
        self,
        db: Session,
        client_id: UUID,
        candidate_id: UUID,
        include_deleted: bool = False
    ) -> List[Application]:
        """Get all applications for a candidate.
        
        Args:
            db: Database session
            client_id: Client UUID
            candidate_id: Candidate UUID
            include_deleted: Whether to include soft-deleted applications
            
        Returns:
            List of applications for the candidate
        """
        return self.repository.get_by_candidate(
            db, client_id, candidate_id, include_deleted
        )
    
    def get_applications_by_status(
        self,
        db: Session,
        client_id: UUID,
        status: str,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Application]:
        """Get applications by status.
        
        Args:
            db: Database session
            client_id: Client UUID
            status: Application status
            skip: Number of records to skip
            limit: Maximum number of records
            include_deleted: Whether to include soft-deleted applications
            
        Returns:
            List of applications with specified status
        """
        return self.repository.get_by_status(
            db, client_id, status, skip, limit, include_deleted
        )
    
    def get_flagged_applications(
        self,
        db: Session,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get flagged applications for review.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of flagged applications
        """
        return self.repository.get_flagged_applications(db, client_id, skip, limit)
    
    def update_application(
        self,
        db: Session,
        application_id: UUID,
        client_id: UUID,
        application_data: ApplicationUpdate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Application]:
        """Update application information with audit logging and real-time events.
        
        Args:
            db: Database session
            application_id: Application UUID
            client_id: Client UUID
            application_data: Application update data
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Updated application if found, None otherwise
        """
        try:
            # Get the current application for comparison
            old_application = self.repository.get_by_id(db, application_id)
            if not old_application:
                return None
            
            # Only update fields that are provided
            update_data = application_data.dict(exclude_unset=True)
            old_job_id = old_application.job_id
            target_job_id = update_data.get("job_id", old_job_id)
            if "job_id" in update_data:
                job_id = update_data.get("job_id")
                if job_id is None:
                    update_data["job_title"] = None
                else:
                    job = (
                        db.query(Job)
                        .filter(Job.id == job_id, Job.client_id == client_id)
                        .first()
                    )
                    if not job:
                        raise ValueError("Job not found for the selected client")
                    if (
                        job_id != old_job_id
                        and (
                            not job.vacant
                            or self._has_filled_application_for_job(db, job_id)
                        )
                    ):
                        raise ValueError("Selected job is no longer vacant")
                    update_data["job_title"] = job.title
            if "status" in update_data:
                update_data["status"] = normalize_application_status(update_data["status"])
                update_data["status_updated_at"] = datetime.utcnow()
            target_status = update_data.get("status", old_application.status)
            if (
                target_job_id is not None
                and target_status in {"HIRED", "SELECTED"}
                and self._has_filled_application_for_job(
                    db,
                    target_job_id,
                    exclude_application_id=old_application.id,
                )
            ):
                raise ValueError("Selected job already has a hired candidate and is filled")
            
            application = self.repository.update_with_audit(
                db=db,
                id=application_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **update_data
            )

            if application:
                self._sync_job_vacancy(db, old_job_id)
                self._sync_job_vacancy(db, application.job_id)
            
            if application:
                logger.info(
                    "Application updated",
                    application_id=str(application_id),
                    client_id=str(client_id),
                    status=application.status
                )
                
                # Publish real-time event for status changes
                if user_id and 'status' in update_data and old_application.status != application.status:
                    try:
                        # Get candidate name for the event
                        candidate_name = "Unknown"
                        if hasattr(application, 'candidate') and application.candidate:
                            candidate_name = application.candidate.name
                        else:
                            # Fallback: query candidate separately
                            from ats_backend.repositories.candidate import CandidateRepository
                            candidate_repo = CandidateRepository()
                            candidate = candidate_repo.get_by_id(db, application.candidate_id)
                            if candidate:
                                candidate_name = candidate.name
                        
                        # Publish status change event asynchronously
                        asyncio.create_task(
                            event_publisher.publish_application_status_changed(
                                tenant_id=client_id,
                                application_id=application.id,
                                old_status=old_application.status,
                                new_status=application.status,
                                candidate_id=application.candidate_id,
                                candidate_name=candidate_name,
                                user_id=user_id,
                                additional_data={
                                    "ip_address": ip_address,
                                    "user_agent": user_agent,
                                    "changes": update_data
                                }
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to publish application status change event",
                            application_id=str(application_id),
                            error=str(e)
                        )
            
            return application
            
        except Exception as e:
            logger.error(
                "Application update failed",
                application_id=str(application_id),
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to update application: {str(e)}")
    
    def soft_delete_application(
        self,
        db: Session,
        application_id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Soft delete an application with audit logging.
        
        Args:
            db: Database session
            application_id: Application UUID
            client_id: Client UUID
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if soft deleted, False if not found
        """
        try:
            existing_application = self.repository.get_by_id(db, application_id)
            affected_job_id = existing_application.job_id if existing_application else None
            deleted = self.repository.soft_delete_with_audit(
                db=db,
                application_id=application_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if deleted:
                self._sync_job_vacancy(db, affected_job_id)
                logger.info(
                    "Application soft deleted",
                    application_id=str(application_id),
                    client_id=str(client_id)
                )
            
            return deleted
            
        except Exception as e:
            logger.error(
                "Application soft deletion failed",
                application_id=str(application_id),
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to soft delete application: {str(e)}")
    
    def restore_application(
        self,
        db: Session,
        application_id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Restore a soft-deleted application with audit logging.
        
        Args:
            db: Database session
            application_id: Application UUID
            client_id: Client UUID
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if restored, False if not found
        """
        try:
            existing_application = self.repository.get_by_id(db, application_id)
            affected_job_id = existing_application.job_id if existing_application else None
            restored = self.repository.restore_with_audit(
                db=db,
                application_id=application_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if restored:
                self._sync_job_vacancy(db, affected_job_id)
                logger.info(
                    "Application restored",
                    application_id=str(application_id),
                    client_id=str(client_id)
                )
            
            return restored
            
        except Exception as e:
            logger.error(
                "Application restoration failed",
                application_id=str(application_id),
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to restore application: {str(e)}")
    
    def flag_application(
        self,
        db: Session,
        application_id: UUID,
        flag_reason: str,
        user_id: Optional[UUID] = None
    ) -> bool:
        """Flag an application for manual review with real-time events.
        
        Args:
            db: Database session
            application_id: Application UUID
            flag_reason: Reason for flagging
            user_id: User who flagged the application (optional)
            
        Returns:
            True if flagged successfully, False if not found
        """
        success = self.repository.flag_for_review(db, application_id, flag_reason)
        
        if success:
            # Publish real-time event
            try:
                # Get application and candidate details
                application = self.repository.get_by_id(db, application_id)
                if application:
                    candidate_name = "Unknown"
                    if hasattr(application, 'candidate') and application.candidate:
                        candidate_name = application.candidate.name
                    else:
                        # Fallback: query candidate separately
                        candidate_repo = CandidateRepository()
                        candidate = candidate_repo.get_by_id(db, application.candidate_id)
                        if candidate:
                            candidate_name = candidate.name
                    
                    # Publish flagged event asynchronously
                    asyncio.create_task(
                        event_publisher.publish_application_flagged(
                            tenant_id=application.client_id,
                            application_id=application.id,
                            candidate_id=application.candidate_id,
                            candidate_name=candidate_name,
                            flag_reason=flag_reason,
                            user_id=user_id
                        )
                    )
            except Exception as e:
                logger.warning(
                    "Failed to publish application flagged event",
                    application_id=str(application_id),
                    error=str(e)
                )
        
        return success
    
    def unflag_application(
        self,
        db: Session,
        application_id: UUID
    ) -> bool:
        """Remove flag from an application.
        
        Args:
            db: Database session
            application_id: Application UUID
            
        Returns:
            True if unflagged successfully, False if not found
        """
        return self.repository.unflag(db, application_id)
    
    def get_active_applications(
        self,
        db: Session,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get all active (non-deleted) applications.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of active applications
        """
        return self.repository.get_active_applications(db, client_id, skip, limit)
    
    def get_deleted_applications(
        self,
        db: Session,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get all soft-deleted applications.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of deleted applications
        """
        return self.repository.get_deleted_applications(db, client_id, skip, limit)
    
    def update_application_status(
        self,
        db: Session,
        application_id: UUID,
        new_status: str,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        force_update: bool = False
    ) -> Optional[Application]:
        """Update application status with workflow progression controls.
        
        Args:
            db: Database session
            application_id: Application UUID
            new_status: New status to set
            client_id: Client UUID
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            force_update: Force update even if workflow progression is blocked
            
        Returns:
            Updated application if successful, None otherwise
            
        Raises:
            ValueError: If workflow progression is not allowed
        """
        try:
            # Check workflow progression unless forced
            if not force_update:
                from ats_backend.services.duplicate_detection_service import DuplicateDetectionService
                duplicate_service = DuplicateDetectionService()
                
                is_allowed, block_reason = duplicate_service.check_workflow_progression_allowed(
                    db, application_id
                )
                
                if not is_allowed:
                    raise ValueError(f"Workflow progression blocked: {block_reason}")
            
            # Update application status
            application_data = ApplicationUpdate(status=new_status)
            return self.update_application(
                db=db,
                application_id=application_id,
                client_id=client_id,
                application_data=application_data,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
        except Exception as e:
            logger.error(
                "Application status update failed",
                application_id=str(application_id),
                new_status=new_status,
                error=str(e)
            )
            raise
    
    def get_application_statistics(
        self,
        db: Session,
        client_id: UUID
    ) -> Dict[str, Any]:
        """Get application statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with application statistics
        """
        stats = {
            "total_applications": self.repository.count(db, {"client_id": client_id}),
            "active_applications": len(self.repository.get_active_applications(db, client_id)),
            "deleted_applications": len(self.repository.get_deleted_applications(db, client_id)),
            "flagged_applications": len(self.repository.get_flagged_applications(db, client_id)),
            "received": self.repository.count_by_status(db, client_id, "RECEIVED"),
            "screening": self.repository.count_by_status(db, client_id, "SCREENING"),
            "interview_scheduled": self.repository.count_by_status(db, client_id, "INTERVIEW_SCHEDULED"),
            "interviewed": self.repository.count_by_status(db, client_id, "INTERVIEWED"),
            "offer_made": self.repository.count_by_status(db, client_id, "OFFER_MADE"),
            "hired": self.repository.count_by_status(db, client_id, "HIRED"),
            "rejected": self.repository.count_by_status(db, client_id, "REJECTED"),
            "withdrawn": self.repository.count_by_status(db, client_id, "WITHDRAWN"),
        }
        
        logger.debug("Application statistics retrieved", client_id=str(client_id), stats=stats)
        return stats

    def acknowledge_hr_interview(
        self,
        db: Session,
        application_id: UUID,
        client_id: UUID,
        acknowledged_by: UUID,
        note: Optional[str] = None,
    ) -> Optional[Application]:
        """Acknowledge that HR interview is complete and candidate is ready for client review."""
        application = self.repository.get_by_id(db, application_id)
        if not application or application.client_id != client_id:
            return None

        candidate = CandidateRepository().get_by_id(db, application.candidate_id)
        if not candidate:
            raise ValueError("Candidate not found for application")

        if not candidate.is_direct_interview:
            raise ValueError("Candidate has no direct interview record")

        interview_exists = (
            db.query(InterviewRecord.id)
            .filter(
                InterviewRecord.candidate_id == application.candidate_id,
                InterviewRecord.client_id == client_id,
                InterviewRecord.company_id == client_id,
                InterviewRecord.deleted_at.is_(None),
            )
            .first()
            is not None
        )
        if not interview_exists:
            raise ValueError("Direct interview record is required before acknowledgement")

        application.hr_interview_acknowledged = True
        application.hr_interview_acknowledged_at = datetime.utcnow()
        application.hr_interview_acknowledged_by = acknowledged_by
        application.hr_interview_ack_note = (note or "").strip() or None
        application.status = "INTERVIEWED"
        application.status_updated_at = datetime.utcnow()
        application.updated_at = datetime.utcnow()
        db.flush()
        return application
