"""Event publisher for real-time SSE notifications."""

from typing import Dict, Any, Optional
from uuid import UUID
import structlog

from .sse_manager import sse_manager

logger = structlog.get_logger(__name__)


class EventPublisher:
    """Publishes events to the SSE system for real-time notifications."""
    
    @staticmethod
    async def publish_application_status_changed(
        tenant_id: UUID,
        application_id: UUID,
        old_status: str,
        new_status: str,
        candidate_id: UUID,
        candidate_name: str,
        user_id: UUID,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish application status change event.
        
        Args:
            tenant_id: Tenant ID
            application_id: Application ID
            old_status: Previous status
            new_status: New status
            candidate_id: Candidate ID
            candidate_name: Candidate name
            user_id: User who made the change
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "application_id": str(application_id),
            "candidate_id": str(candidate_id),
            "candidate_name": candidate_name,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": str(user_id),
            "change_type": "status_change"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="application_status_changed",
                data=event_data,
                tenant_id=tenant_id,
                application_id=application_id
            )
            
            if success:
                logger.info(
                    "Application status change event published",
                    tenant_id=str(tenant_id),
                    application_id=str(application_id),
                    old_status=old_status,
                    new_status=new_status
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish application status change event",
                tenant_id=str(tenant_id),
                application_id=str(application_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    async def publish_application_created(
        tenant_id: UUID,
        application_id: UUID,
        candidate_id: UUID,
        candidate_name: str,
        status: str,
        user_id: UUID,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish application created event.
        
        Args:
            tenant_id: Tenant ID
            application_id: Application ID
            candidate_id: Candidate ID
            candidate_name: Candidate name
            status: Initial status
            user_id: User who created the application
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "application_id": str(application_id),
            "candidate_id": str(candidate_id),
            "candidate_name": candidate_name,
            "status": status,
            "created_by": str(user_id),
            "change_type": "created"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="application_created",
                data=event_data,
                tenant_id=tenant_id,
                application_id=application_id
            )
            
            if success:
                logger.info(
                    "Application created event published",
                    tenant_id=str(tenant_id),
                    application_id=str(application_id),
                    candidate_name=candidate_name
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish application created event",
                tenant_id=str(tenant_id),
                application_id=str(application_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    async def publish_application_flagged(
        tenant_id: UUID,
        application_id: UUID,
        candidate_id: UUID,
        candidate_name: str,
        flag_reason: str,
        user_id: Optional[UUID] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish application flagged event.
        
        Args:
            tenant_id: Tenant ID
            application_id: Application ID
            candidate_id: Candidate ID
            candidate_name: Candidate name
            flag_reason: Reason for flagging
            user_id: User who flagged (if manual)
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "application_id": str(application_id),
            "candidate_id": str(candidate_id),
            "candidate_name": candidate_name,
            "flag_reason": flag_reason,
            "flagged_by": str(user_id) if user_id else "system",
            "change_type": "flagged"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="application_flagged",
                data=event_data,
                tenant_id=tenant_id,
                application_id=application_id
            )
            
            if success:
                logger.info(
                    "Application flagged event published",
                    tenant_id=str(tenant_id),
                    application_id=str(application_id),
                    flag_reason=flag_reason
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish application flagged event",
                tenant_id=str(tenant_id),
                application_id=str(application_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    async def publish_candidate_created(
        tenant_id: UUID,
        candidate_id: UUID,
        candidate_name: str,
        candidate_email: str,
        user_id: UUID,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish candidate created event.
        
        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            candidate_name: Candidate name
            candidate_email: Candidate email
            user_id: User who created the candidate
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "candidate_id": str(candidate_id),
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "created_by": str(user_id),
            "change_type": "created"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="candidate_created",
                data=event_data,
                tenant_id=tenant_id
            )
            
            if success:
                logger.info(
                    "Candidate created event published",
                    tenant_id=str(tenant_id),
                    candidate_id=str(candidate_id),
                    candidate_name=candidate_name
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish candidate created event",
                tenant_id=str(tenant_id),
                candidate_id=str(candidate_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    async def publish_candidate_updated(
        tenant_id: UUID,
        candidate_id: UUID,
        candidate_name: str,
        changes: Dict[str, Any],
        user_id: UUID,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish candidate updated event.
        
        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            candidate_name: Candidate name
            changes: Dictionary of changed fields
            user_id: User who updated the candidate
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "candidate_id": str(candidate_id),
            "candidate_name": candidate_name,
            "changes": changes,
            "updated_by": str(user_id),
            "change_type": "updated"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="candidate_updated",
                data=event_data,
                tenant_id=tenant_id
            )
            
            if success:
                logger.info(
                    "Candidate updated event published",
                    tenant_id=str(tenant_id),
                    candidate_id=str(candidate_id),
                    changes=list(changes.keys())
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish candidate updated event",
                tenant_id=str(tenant_id),
                candidate_id=str(candidate_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    async def publish_resume_processed(
        tenant_id: UUID,
        candidate_id: UUID,
        candidate_name: str,
        resume_id: UUID,
        processing_status: str,
        processing_time_ms: float,
        used_ocr: bool = False,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish resume processed event.
        
        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            candidate_name: Candidate name
            resume_id: Resume ID
            processing_status: Processing status (success, failed, etc.)
            processing_time_ms: Processing time in milliseconds
            used_ocr: Whether OCR was used
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "candidate_id": str(candidate_id),
            "candidate_name": candidate_name,
            "resume_id": str(resume_id),
            "processing_status": processing_status,
            "processing_time_ms": processing_time_ms,
            "used_ocr": used_ocr,
            "change_type": "resume_processed"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="resume_processed",
                data=event_data,
                tenant_id=tenant_id
            )
            
            if success:
                logger.info(
                    "Resume processed event published",
                    tenant_id=str(tenant_id),
                    candidate_id=str(candidate_id),
                    processing_status=processing_status,
                    processing_time_ms=processing_time_ms
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish resume processed event",
                tenant_id=str(tenant_id),
                candidate_id=str(candidate_id),
                error=str(e)
            )
            return False
    
    @staticmethod
    async def publish_system_alert(
        tenant_id: UUID,
        alert_type: str,
        alert_level: str,
        message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish system alert event.
        
        Args:
            tenant_id: Tenant ID
            alert_type: Type of alert (performance, security, etc.)
            alert_level: Alert level (info, warning, error, critical)
            message: Alert message
            additional_data: Additional event data
            
        Returns:
            True if event was published successfully
        """
        event_data = {
            "alert_type": alert_type,
            "alert_level": alert_level,
            "message": message,
            "change_type": "system_alert"
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        try:
            success = await sse_manager.publish_event(
                event_type="system_alert",
                data=event_data,
                tenant_id=tenant_id
            )
            
            if success:
                logger.info(
                    "System alert event published",
                    tenant_id=str(tenant_id),
                    alert_type=alert_type,
                    alert_level=alert_level
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to publish system alert event",
                tenant_id=str(tenant_id),
                alert_type=alert_type,
                error=str(e)
            )
            return False


# Global event publisher instance
event_publisher = EventPublisher()