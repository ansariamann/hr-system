"""Application management service."""

import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.application import Application
from ats_backend.repositories.application import ApplicationRepository
from ats_backend.schemas.application import ApplicationCreate, ApplicationUpdate
from ats_backend.core.event_publisher import event_publisher

logger = structlog.get_logger(__name__)


class ApplicationService:
    """Service for managing application operations."""
    
    def __init__(self):
        self.repository = ApplicationRepository()
    
    def create_application(
        self,
        db: Session,
        client_id: UUID,
        application_data: ApplicationCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
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
            application = self.repository.create_with_audit(
                db=db,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **application_data.dict()
            )
            
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
                        from ats_backend.repositories.candidate import CandidateRepository
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
            deleted = self.repository.soft_delete_with_audit(
                db=db,
                application_id=application_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if deleted:
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
            restored = self.repository.restore_with_audit(
                db=db,
                application_id=application_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if restored:
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
                        from ats_backend.repositories.candidate import CandidateRepository
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