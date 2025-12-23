"""Candidate management service."""

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.candidate import Candidate
from ats_backend.repositories.candidate import CandidateRepository
from ats_backend.schemas.candidate import CandidateCreate, CandidateUpdate

logger = structlog.get_logger(__name__)


class CandidateService:
    """Service for managing candidate operations."""
    
    def __init__(self):
        self.repository = CandidateRepository()
    
    def create_candidate(
        self,
        db: Session,
        client_id: UUID,
        candidate_data: CandidateCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Candidate:
        """Create a new candidate with audit logging.
        
        Args:
            db: Database session
            client_id: Client UUID
            candidate_data: Candidate creation data
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created candidate
            
        Raises:
            ValueError: If candidate creation fails
        """
        try:
            candidate = self.repository.create_with_audit(
                db=db,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **candidate_data.dict()
            )
            
            logger.info(
                "Candidate created",
                candidate_id=str(candidate.id),
                client_id=str(client_id),
                name=candidate.name
            )
            return candidate
            
        except Exception as e:
            logger.error(
                "Candidate creation failed",
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to create candidate: {str(e)}")
    
    def get_candidate_by_id(
        self, 
        db: Session, 
        candidate_id: UUID
    ) -> Optional[Candidate]:
        """Get candidate by ID.
        
        Args:
            db: Database session
            candidate_id: Candidate UUID
            
        Returns:
            Candidate if found, None otherwise
        """
        return self.repository.get_by_id(db, candidate_id)
    
    def get_candidate_by_email(
        self, 
        db: Session, 
        client_id: UUID, 
        email: str
    ) -> Optional[Candidate]:
        """Get candidate by email within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            email: Candidate email
            
        Returns:
            Candidate if found, None otherwise
        """
        return self.repository.get_by_email(db, client_id, email)
    
    def search_candidates(
        self,
        db: Session,
        client_id: UUID,
        name_pattern: Optional[str] = None,
        skills: Optional[List[str]] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Candidate]:
        """Search candidates with various filters.
        
        Args:
            db: Database session
            client_id: Client UUID
            name_pattern: Name pattern to search for (optional)
            skills: List of skills to search for (optional)
            status: Candidate status filter (optional)
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of matching candidates
        """
        if name_pattern:
            return self.repository.search_by_name(db, client_id, name_pattern, limit)
        elif skills:
            return self.repository.search_by_skills(db, client_id, skills, limit)
        elif status:
            return self.repository.get_by_status(db, client_id, status, skip, limit)
        else:
            return self.repository.get_multi(
                db, skip, limit, {"client_id": client_id}
            )
    
    def update_candidate(
        self,
        db: Session,
        candidate_id: UUID,
        client_id: UUID,
        candidate_data: CandidateUpdate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Candidate]:
        """Update candidate information with audit logging.
        
        Args:
            db: Database session
            candidate_id: Candidate UUID
            client_id: Client UUID
            candidate_data: Candidate update data
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Updated candidate if found, None otherwise
        """
        try:
            # Only update fields that are provided
            update_data = candidate_data.dict(exclude_unset=True)
            
            candidate = self.repository.update_with_audit(
                db=db,
                id=candidate_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                **update_data
            )
            
            if candidate:
                logger.info(
                    "Candidate updated",
                    candidate_id=str(candidate_id),
                    client_id=str(client_id)
                )
            
            return candidate
            
        except Exception as e:
            logger.error(
                "Candidate update failed",
                candidate_id=str(candidate_id),
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to update candidate: {str(e)}")
    
    def delete_candidate(
        self,
        db: Session,
        candidate_id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Delete a candidate with audit logging.
        
        Args:
            db: Database session
            candidate_id: Candidate UUID
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
                id=candidate_id,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if deleted:
                logger.info(
                    "Candidate deleted",
                    candidate_id=str(candidate_id),
                    client_id=str(client_id)
                )
            
            return deleted
            
        except Exception as e:
            logger.error(
                "Candidate deletion failed",
                candidate_id=str(candidate_id),
                client_id=str(client_id),
                error=str(e)
            )
            raise ValueError(f"Failed to delete candidate: {str(e)}")
    
    def find_potential_duplicates(
        self,
        db: Session,
        client_id: UUID,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> List[Candidate]:
        """Find potential duplicate candidates.
        
        Args:
            db: Database session
            client_id: Client UUID
            name: Candidate name
            email: Candidate email (optional)
            phone: Candidate phone (optional)
            
        Returns:
            List of potential duplicate candidates
        """
        return self.repository.find_potential_duplicates(
            db, client_id, name, email, phone
        )
    
    def get_candidates_with_applications(
        self,
        db: Session,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Candidate]:
        """Get candidates with their applications.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of candidates with loaded applications
        """
        return self.repository.get_candidates_with_applications(
            db, client_id, skip, limit
        )
    
    def update_candidate_hash(
        self,
        db: Session,
        candidate_id: UUID,
        candidate_hash: str
    ) -> bool:
        """Update candidate hash for duplicate detection.
        
        Args:
            db: Database session
            candidate_id: Candidate UUID
            candidate_hash: New candidate hash
            
        Returns:
            True if updated successfully, False if candidate not found
        """
        return self.repository.update_candidate_hash(db, candidate_id, candidate_hash)
    
    def get_candidate_statistics(
        self,
        db: Session,
        client_id: UUID
    ) -> Dict[str, Any]:
        """Get candidate statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with candidate statistics
        """
        stats = {
            "total_candidates": self.repository.count(db, {"client_id": client_id}),
            "active_candidates": len(self.repository.get_by_status(db, client_id, "ACTIVE")),
            "inactive_candidates": len(self.repository.get_by_status(db, client_id, "INACTIVE")),
            "hired_candidates": len(self.repository.get_by_status(db, client_id, "HIRED")),
            "left_candidates": len(self.repository.get_by_status(db, client_id, "LEFT")),
        }
        
        logger.debug("Candidate statistics retrieved", client_id=str(client_id), stats=stats)
        return stats