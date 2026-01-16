"""Candidate repository for database operations."""

from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, cast, Integer
from sqlalchemy.dialects.postgresql import JSONB
import structlog

from ats_backend.models.candidate import Candidate
from .audited_base import AuditedRepository

logger = structlog.get_logger(__name__)


class CandidateRepository(AuditedRepository[Candidate]):
    """Repository for Candidate model operations."""
    
    def __init__(self):
        super().__init__(Candidate)
    
    def get_by_email(self, db: Session, client_id: UUID, email: str) -> Optional[Candidate]:
        """Get candidate by email within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            email: Candidate email
            
        Returns:
            Candidate if found, None otherwise
        """
        return db.query(Candidate).filter(
            and_(
                Candidate.client_id == client_id,
                Candidate.email == email
            )
        ).first()
    
    def get_by_phone(self, db: Session, client_id: UUID, phone: str) -> Optional[Candidate]:
        """Get candidate by phone within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            phone: Candidate phone
            
        Returns:
            Candidate if found, None otherwise
        """
        return db.query(Candidate).filter(
            and_(
                Candidate.client_id == client_id,
                Candidate.phone == phone
            )
        ).first()
    
    def get_by_hash(self, db: Session, client_id: UUID, candidate_hash: str) -> Optional[Candidate]:
        """Get candidate by hash within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            candidate_hash: Candidate hash for duplicate detection
            
        Returns:
            Candidate if found, None otherwise
        """
        return db.query(Candidate).filter(
            and_(
                Candidate.client_id == client_id,
                Candidate.candidate_hash == candidate_hash
            )
        ).first()
    
    def search(
        self, 
        db: Session, 
        client_id: UUID, 
        name_pattern: Optional[str] = None, 
        skills: Optional[List[str]] = None, 
        location: Optional[str] = None,
        max_experience: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Candidate]:
        """Search candidates with combined filters.
        
        Args:
            db: Database session
            client_id: Client UUID
            name_pattern: Name pattern to search for (ilike)
            skills: List of skills to search for (contains)
            location: Location pattern to search for (ilike)
            max_experience: Maximum years of experience (<=)
            status: Candidate status filter
            skip: Number of records to skip
            limit: Maximum number of results
            
        Returns:
            List of matching candidates
        """
        conditions = [Candidate.client_id == client_id]
        
        if name_pattern:
            conditions.append(Candidate.name.ilike(f"%{name_pattern}%"))
            
        if location:
            conditions.append(Candidate.location.ilike(f"%{location}%"))
            
        if status:
            conditions.append(Candidate.status == status)
            
        if skills:
            # Use JSONB contains operator to search for ANY of the skills
            # Or should it be ALL? "Python, React" usually implies AND or OR depending on UX.
            # Let's assume OR for broad search, or loop for AND.
            # The previous implementation was OR. Let's stick with OR for now?
            # User request: "filters such as city,skills,etc".
            # Usually skill search is "Find someone who knows Python OR default matches".
            # But "Python, React" usually implies finding a fullstack dev (AND).
            # Let's stick with the previous OR implementation logic but adaptable.
            # Actually, previous implementation used OR.
            skill_conditions = []
            for skill in skills:
                skill_conditions.append(
                    Candidate.skills.op('@>')({'skills': [skill]})
                )
            if skill_conditions:
                conditions.append(or_(*skill_conditions))
        
        if max_experience is not None:
             # Query JSONB: experience->'years' <= max_experience
             # We need to cast it to integer.
             # Note: This assumes experience is stored as {"years": 5}.
             conditions.append(
                 cast(Candidate.experience['years'].astext, Integer) <= max_experience
             )
        
        return (
            db.query(Candidate)
            .filter(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .all()
        )

    # Legacy methods kept for compatibility but should be deprecated or refactored to use search()
    def search_by_name(self, db: Session, client_id: UUID, name_pattern: str, limit: int = 10) -> List[Candidate]:
        return self.search(db, client_id, name_pattern=name_pattern, limit=limit)
    
    def search_by_skills(self, db: Session, client_id: UUID, skills: List[str], limit: int = 10) -> List[Candidate]:
        return self.search(db, client_id, skills=skills, limit=limit)
    
    def get_by_status(self, db: Session, client_id: UUID, status: str, skip: int = 0, limit: int = 100) -> List[Candidate]:
        return self.search(db, client_id, status=status, skip=skip, limit=limit)
    
    def find_potential_duplicates(
        self, 
        db: Session, 
        client_id: UUID, 
        name: str, 
        email: Optional[str] = None, 
        phone: Optional[str] = None
    ) -> List[Candidate]:
        """Find potential duplicate candidates using fuzzy matching.
        
        Args:
            db: Database session
            client_id: Client UUID
            name: Candidate name
            email: Candidate email (optional)
            phone: Candidate phone (optional)
            
        Returns:
            List of potential duplicate candidates
        """
        conditions = [Candidate.client_id == client_id]
        
        # Name similarity (case-insensitive partial match)
        name_condition = Candidate.name.ilike(f"%{name}%")
        
        # Email exact match
        email_condition = None
        if email:
            email_condition = Candidate.email == email
        
        # Phone exact match
        phone_condition = None
        if phone:
            phone_condition = Candidate.phone == phone
        
        # Combine conditions with OR logic for potential matches
        match_conditions = [name_condition]
        if email_condition:
            match_conditions.append(email_condition)
        if phone_condition:
            match_conditions.append(phone_condition)
        
        conditions.append(or_(*match_conditions))
        
        return db.query(Candidate).filter(and_(*conditions)).all()
    
    def get_candidates_with_applications(
        self, 
        db: Session, 
        client_id: UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Candidate]:
        """Get candidates with their applications within client context.
        
        Args:
            db: Database session
            client_id: Client UUID
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of candidates with loaded applications
        """
        from sqlalchemy.orm import joinedload
        
        return (
            db.query(Candidate)
            .options(joinedload(Candidate.applications))
            .filter(Candidate.client_id == client_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_candidates_by_hash_pattern(
        self, 
        db: Session, 
        client_id: UUID, 
        hash_prefix: str, 
        limit: int = 10
    ) -> List[Candidate]:
        """Get candidates with similar hash patterns for advanced duplicate detection.
        
        Args:
            db: Database session
            client_id: Client UUID
            hash_prefix: Hash prefix to search for
            limit: Maximum number of results
            
        Returns:
            List of candidates with similar hash patterns
        """
        return (
            db.query(Candidate)
            .filter(
                and_(
                    Candidate.client_id == client_id,
                    Candidate.candidate_hash.like(f"{hash_prefix}%")
                )
            )
            .limit(limit)
            .all()
        )
    
    def get_candidates_without_hash(
        self, 
        db: Session, 
        client_id: UUID, 
        limit: int = 100
    ) -> List[Candidate]:
        """Get candidates without hash values for batch processing.
        
        Args:
            db: Database session
            client_id: Client UUID
            limit: Maximum number of results
            
        Returns:
            List of candidates without hash values
        """
        return (
            db.query(Candidate)
            .filter(
                and_(
                    Candidate.client_id == client_id,
                    or_(
                        Candidate.candidate_hash.is_(None),
                        Candidate.candidate_hash == ""
                    )
                )
            )
            .limit(limit)
            .all()
        )
    
    def find_exact_matches(
        self, 
        db: Session, 
        client_id: UUID, 
        name: Optional[str] = None,
        email: Optional[str] = None, 
        phone: Optional[str] = None
    ) -> List[Candidate]:
        """Find candidates with exact field matches.
        
        Args:
            db: Database session
            client_id: Client UUID
            name: Exact name to match (optional)
            email: Exact email to match (optional)
            phone: Exact phone to match (optional)
            
        Returns:
            List of candidates with exact matches
        """
        conditions = [Candidate.client_id == client_id]
        
        if name:
            conditions.append(Candidate.name == name)
        if email:
            conditions.append(Candidate.email == email)
        if phone:
            conditions.append(Candidate.phone == phone)
        
        # Need at least one search criterion besides client_id
        if len(conditions) == 1:
            return []
        
        return db.query(Candidate).filter(and_(*conditions)).all()
    
    def update_candidate_hash(self, db: Session, candidate_id: UUID, candidate_hash: str) -> bool:
        """Update candidate hash for duplicate detection.
        
        Args:
            db: Database session
            candidate_id: Candidate UUID
            candidate_hash: New candidate hash
            
        Returns:
            True if updated successfully, False if candidate not found
        """
        candidate = self.get_by_id(db, candidate_id)
        if not candidate:
            return False
        
        candidate.candidate_hash = candidate_hash
        db.commit()
        
        logger.info("Candidate hash updated", candidate_id=str(candidate_id))
        return True