"""Candidate repository for database operations."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, cast, Integer, String
import structlog

from ats_backend.models.candidate import Candidate
from .audited_base import AuditedRepository

logger = structlog.get_logger(__name__)


class CandidateRepository(AuditedRepository[Candidate]):
    """Repository for Candidate model operations."""

    def __init__(self):
        super().__init__(Candidate)

    def get_by_email(self, db: Session, client_id: UUID, email: str) -> Optional[Candidate]:
        return db.query(Candidate).filter(
            and_(Candidate.client_id == client_id, Candidate.email == email)
        ).first()

    def get_by_phone(self, db: Session, client_id: UUID, phone: str) -> Optional[Candidate]:
        return db.query(Candidate).filter(
            and_(Candidate.client_id == client_id, Candidate.phone == phone)
        ).first()

    def get_by_hash(self, db: Session, client_id: UUID, candidate_hash: str) -> Optional[Candidate]:
        return db.query(Candidate).filter(
            and_(Candidate.client_id == client_id, Candidate.candidate_hash == candidate_hash)
        ).first()

    def search(
        self,
        db: Session,
        client_id: UUID,
        name_pattern: Optional[str] = None,
        skills: Optional[List[str]] = None,
        location: Optional[str] = None,
        min_experience: Optional[int] = None,
        max_experience: Optional[int] = None,
        min_ctc_current: Optional[float] = None,
        max_ctc_current: Optional[float] = None,
        min_ctc_expected: Optional[float] = None,
        max_ctc_expected: Optional[float] = None,
        status: Optional[str] = None,
        assigned_user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Candidate]:
        """Search candidates with combined filters."""
        conditions = [Candidate.client_id == client_id]

        if name_pattern:
            pattern = f"%{name_pattern}%"
            conditions.append(
                or_(
                    Candidate.name.ilike(pattern),
                    Candidate.email.ilike(pattern),
                    Candidate.location.ilike(pattern),
                    cast(Candidate.skills, String).ilike(pattern),
                )
            )

        if location:
            conditions.append(Candidate.location.ilike(f"%{location}%"))

        if status:
            conditions.append(Candidate.status == status)
        if assigned_user_id is not None:
            conditions.append(Candidate.assigned_user_id == assigned_user_id)

        if skills:
            skill_conditions = [
                cast(Candidate.skills, String).ilike(f"%{skill}%")
                for skill in skills
                if skill
            ]
            if skill_conditions:
                conditions.append(or_(*skill_conditions))

        if min_experience is not None:
            conditions.append(cast(Candidate.experience["years"], Integer) >= min_experience)
        if max_experience is not None:
            conditions.append(cast(Candidate.experience["years"], Integer) <= max_experience)

        if min_ctc_current is not None:
            conditions.append(Candidate.ctc_current >= min_ctc_current)
        if max_ctc_current is not None:
            conditions.append(Candidate.ctc_current <= max_ctc_current)
        if min_ctc_expected is not None:
            conditions.append(Candidate.ctc_expected >= min_ctc_expected)
        if max_ctc_expected is not None:
            conditions.append(Candidate.ctc_expected <= max_ctc_expected)

        return (
            db.query(Candidate)
            .filter(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_for_client(self, db: Session, candidate_id: UUID, client_id: UUID) -> Optional[Candidate]:
        return db.query(Candidate).filter(
            and_(Candidate.id == candidate_id, Candidate.client_id == client_id)
        ).first()

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
        phone: Optional[str] = None,
    ) -> List[Candidate]:
        conditions = [Candidate.client_id == client_id]
        name_condition = Candidate.name.ilike(f"%{name}%")
        match_conditions = [name_condition]
        if email:
            match_conditions.append(Candidate.email == email)
        if phone:
            match_conditions.append(Candidate.phone == phone)
        conditions.append(or_(*match_conditions))
        return db.query(Candidate).filter(and_(*conditions)).all()

    def get_candidates_with_applications(
        self, db: Session, client_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Candidate]:
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
        self, db: Session, client_id: UUID, hash_prefix: str, limit: int = 10
    ) -> List[Candidate]:
        return (
            db.query(Candidate)
            .filter(and_(Candidate.client_id == client_id, Candidate.candidate_hash.like(f"{hash_prefix}%")))
            .limit(limit)
            .all()
        )

    def get_candidates_without_hash(self, db: Session, client_id: UUID, limit: int = 100) -> List[Candidate]:
        return (
            db.query(Candidate)
            .filter(
                and_(
                    Candidate.client_id == client_id,
                    or_(Candidate.candidate_hash.is_(None), Candidate.candidate_hash == ""),
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
        phone: Optional[str] = None,
    ) -> List[Candidate]:
        conditions = [Candidate.client_id == client_id]
        if name:
            conditions.append(Candidate.name == name)
        if email:
            conditions.append(Candidate.email == email)
        if phone:
            conditions.append(Candidate.phone == phone)
        if len(conditions) == 1:
            return []
        return db.query(Candidate).filter(and_(*conditions)).all()

    def update_candidate_hash(self, db: Session, candidate_id: UUID, candidate_hash: str) -> bool:
        candidate = self.get_by_id(db, candidate_id)
        if not candidate:
            return False
        candidate.candidate_hash = candidate_hash
        db.flush()
        logger.info("Candidate hash updated", candidate_id=str(candidate_id))
        return True
