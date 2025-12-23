"""Application repository for database operations."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_
import structlog

from ats_backend.models.application import Application
from .audited_base import AuditedRepository

logger = structlog.get_logger(__name__)


class ApplicationRepository(AuditedRepository[Application]):
    """Repository for Application model operations."""
    
    def __init__(self):
        super().__init__(Application)
    
    def get_by_candidate(
        self, 
        db: Session, 
        client_id: UUID, 
        candidate_id: UUID,
        include_deleted: bool = False
    ) -> List[Application]:
        """Get all applications for a candidate within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            candidate_id: Candidate UUID
            include_deleted: Whether to include soft-deleted applications
            
        Returns:
            List of applications for the candidate
        """
        query = db.query(Application).filter(
            and_(
                Application.client_id == client_id,
                Application.candidate_id == candidate_id
            )
        )
        
        if not include_deleted:
            query = query.filter(Application.deleted_at.is_(None))
        
        return query.all()
    
    def get_by_status(
        self, 
        db: Session, 
        client_id: UUID, 
        status: str,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Application]:
        """Get applications by status within client context.
        
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
        query = db.query(Application).filter(
            and_(
                Application.client_id == client_id,
                Application.status == status
            )
        )
        
        if not include_deleted:
            query = query.filter(Application.deleted_at.is_(None))
        
        return query.offset(skip).limit(limit).all()
    
    def get_flagged_applications(
        self, 
        db: Session, 
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get flagged applications within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of flagged applications
        """
        return (
            db.query(Application)
            .filter(
                and_(
                    Application.client_id == client_id,
                    Application.flagged_for_review == True,
                    Application.deleted_at.is_(None)
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def soft_delete(self, db: Session, application_id: UUID) -> bool:
        """Soft delete an application by setting deleted_at timestamp.
        
        Args:
            db: Database session
            application_id: Application UUID
            
        Returns:
            True if soft deleted successfully, False if not found
        """
        application = self.get_by_id(db, application_id)
        if not application:
            logger.warning("Application not found for soft delete", application_id=str(application_id))
            return False
        
        if application.deleted_at is not None:
            logger.warning("Application already soft deleted", application_id=str(application_id))
            return True
        
        application.soft_delete()
        db.commit()
        
        logger.info(
            "Application soft deleted",
            application_id=str(application_id),
            candidate_id=str(application.candidate_id)
        )
        return True
    
    def soft_delete_with_audit(
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
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if soft deleted successfully, False if not found
        """
        return super().soft_delete_with_audit(
            db=db,
            id=application_id,
            client_id=client_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def restore(self, db: Session, application_id: UUID) -> bool:
        """Restore a soft-deleted application.
        
        Args:
            db: Database session
            application_id: Application UUID
            
        Returns:
            True if restored successfully, False if not found
        """
        application = self.get_by_id(db, application_id)
        if not application:
            logger.warning("Application not found for restore", application_id=str(application_id))
            return False
        
        if application.deleted_at is None:
            logger.warning("Application is not deleted", application_id=str(application_id))
            return True
        
        application.deleted_at = None
        db.commit()
        
        logger.info(
            "Application restored",
            application_id=str(application_id),
            candidate_id=str(application.candidate_id)
        )
        return True
    
    def restore_with_audit(
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
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if restored successfully, False if not found
        """
        return super().restore_with_audit(
            db=db,
            id=application_id,
            client_id=client_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def get_active_applications(
        self, 
        db: Session, 
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get all active (non-deleted) applications within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of active applications
        """
        return (
            db.query(Application)
            .filter(
                and_(
                    Application.client_id == client_id,
                    Application.deleted_at.is_(None)
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_deleted_applications(
        self, 
        db: Session, 
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get all soft-deleted applications within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of deleted applications
        """
        return (
            db.query(Application)
            .filter(
                and_(
                    Application.client_id == client_id,
                    Application.deleted_at.isnot(None)
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def flag_for_review(
        self, 
        db: Session, 
        application_id: UUID, 
        flag_reason: str
    ) -> bool:
        """Flag an application for manual review.
        
        Args:
            db: Database session
            application_id: Application UUID
            flag_reason: Reason for flagging
            
        Returns:
            True if flagged successfully, False if not found
        """
        application = self.get_by_id(db, application_id)
        if not application:
            logger.warning("Application not found for flagging", application_id=str(application_id))
            return False
        
        application.flagged_for_review = True
        application.flag_reason = flag_reason
        db.commit()
        
        logger.info(
            "Application flagged for review",
            application_id=str(application_id),
            flag_reason=flag_reason
        )
        return True
    
    def unflag(self, db: Session, application_id: UUID) -> bool:
        """Remove flag from an application.
        
        Args:
            db: Database session
            application_id: Application UUID
            
        Returns:
            True if unflagged successfully, False if not found
        """
        application = self.get_by_id(db, application_id)
        if not application:
            logger.warning("Application not found for unflagging", application_id=str(application_id))
            return False
        
        application.flagged_for_review = False
        application.flag_reason = None
        db.commit()
        
        logger.info("Application unflagged", application_id=str(application_id))
        return True
    
    def count_by_status(self, db: Session, client_id: UUID, status: str) -> int:
        """Count applications by status within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            status: Application status
            
        Returns:
            Number of applications with specified status
        """
        return (
            db.query(Application)
            .filter(
                and_(
                    Application.client_id == client_id,
                    Application.status == status,
                    Application.deleted_at.is_(None)
                )
            )
            .count()
        )