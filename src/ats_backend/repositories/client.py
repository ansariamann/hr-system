"""Client repository for database operations."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.client import Client
from .audited_base import AuditedRepository

logger = structlog.get_logger(__name__)


class ClientRepository(AuditedRepository[Client]):
    """Repository for Client model operations."""
    
    def __init__(self):
        super().__init__(Client)
    
    def get_by_name(self, db: Session, name: str) -> Optional[Client]:
        """Get client by name.
        
        Args:
            db: Database session
            name: Client name
            
        Returns:
            Client if found, None otherwise
        """
        return db.query(Client).filter(Client.name == name).first()
    
    def get_by_email_domain(self, db: Session, email_domain: str) -> Optional[Client]:
        """Get client by email domain.
        
        Args:
            db: Database session
            email_domain: Email domain
            
        Returns:
            Client if found, None otherwise
        """
        return db.query(Client).filter(Client.email_domain == email_domain).first()
    
    def search_by_name(self, db: Session, name_pattern: str, limit: int = 10) -> List[Client]:
        """Search clients by name pattern.
        
        Args:
            db: Database session
            name_pattern: Name pattern to search for
            limit: Maximum number of results
            
        Returns:
            List of matching clients
        """
        return (
            db.query(Client)
            .filter(Client.name.ilike(f"%{name_pattern}%"))
            .limit(limit)
            .all()
        )
    
    def get_client_with_stats(self, db: Session, client_id: UUID) -> Optional[dict]:
        """Get client with associated statistics.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with client data and statistics, None if not found
        """
        from ats_backend.models.candidate import Candidate
        from ats_backend.models.application import Application
        from ats_backend.models.resume_job import ResumeJob
        from ats_backend.auth.models import User
        
        client = self.get_by_id(db, client_id)
        if not client:
            return None
        
        stats = {
            "client": client,
            "total_users": db.query(User).filter(User.client_id == client_id).count(),
            "total_candidates": db.query(Candidate).filter(Candidate.client_id == client_id).count(),
            "total_applications": db.query(Application).filter(Application.client_id == client_id).count(),
            "active_applications": db.query(Application).filter(
                Application.client_id == client_id,
                Application.deleted_at.is_(None)
            ).count(),
            "total_resume_jobs": db.query(ResumeJob).filter(ResumeJob.client_id == client_id).count(),
            "pending_resume_jobs": db.query(ResumeJob).filter(
                ResumeJob.client_id == client_id,
                ResumeJob.status == "PENDING"
            ).count(),
        }
        
        logger.debug("Client stats retrieved", client_id=str(client_id), stats=stats)
        return stats