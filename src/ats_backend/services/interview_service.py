"""Service for managing interview records."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.activity_log import ActivityLog
from ats_backend.models.candidate import Candidate
from ats_backend.models.interview_record import InterviewRecord

logger = structlog.get_logger(__name__)


class InterviewService:
    """Service for managing candidate interview records."""

    @staticmethod
    def normalize_skills(skills: Optional[List[str]]) -> Optional[List[str]]:
        if skills is None:
            return None
        normalized = [skill.strip() for skill in skills if isinstance(skill, str) and skill.strip()]
        return normalized or []

    @staticmethod
    def normalize_interview_datetime(value: datetime) -> datetime:
        """Store datetimes as naive UTC consistently."""
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @classmethod
    def validate_interview_datetime(
        cls,
        interview_date: datetime,
        candidate_created_at: Optional[datetime] = None,
    ) -> datetime:
        normalized = cls.normalize_interview_datetime(interview_date)
        now = datetime.utcnow()
        if normalized < now - timedelta(days=365 * 5) or normalized > now + timedelta(days=365 * 5):
            raise ValueError("Interview date must be within 5 years of today")
        if candidate_created_at and normalized < candidate_created_at:
            raise ValueError("Interview date cannot be earlier than candidate creation date")
        return normalized

    def find_duplicate_interview(
        self,
        db: Session,
        candidate_id: UUID,
        client_id: UUID,
        company_id: UUID,
        interview_date: datetime,
        exclude_interview_id: Optional[UUID] = None,
    ) -> Optional[InterviewRecord]:
        query = (
            db.query(InterviewRecord)
            .filter(
                InterviewRecord.candidate_id == candidate_id,
                InterviewRecord.client_id == client_id,
                InterviewRecord.company_id == company_id,
                InterviewRecord.interview_date == interview_date,
                InterviewRecord.deleted_at.is_(None),
            )
        )
        if exclude_interview_id is not None:
            query = query.filter(InterviewRecord.id != exclude_interview_id)
        return query.first()
    
    def record_interview(
        self,
        db: Session,
        candidate: Candidate,
        client_id: UUID,
        company_id: UUID,
        interviewer_id: UUID,
        interview_date: datetime,
        position: Optional[str] = None,
        skills: Optional[List[str]] = None,
        notes: Optional[str] = None,
        rating: Optional[int] = None,
        log_activity: bool = False,
    ) -> InterviewRecord:
        """Record a direct interview with a candidate.
        
        Args:
            db: Database session
            candidate_id: ID of candidate being interviewed
            client_id: ID of client (tenant)
            company_id: ID of company for placement
            interviewer_id: ID of user conducting interview
            interview_date: ISO format datetime string
            notes: Interview notes/feedback
            rating: Interview rating (1-5)
            
        Returns:
            Created InterviewRecord
            
        Raises:
            ValueError: If rating is invalid (not 1-5)
        """
        if rating is not None and (rating < 1 or rating > 5):
            raise ValueError("Interview rating must be between 1 and 5")

        try:
            if candidate.status != "ACTIVE":
                raise ValueError("Candidate must be in ACTIVE status to conduct direct interview")

            normalized_date = self.validate_interview_datetime(
                interview_date,
                candidate_created_at=candidate.created_at,
            )
            existing = self.find_duplicate_interview(
                db=db,
                candidate_id=candidate.id,
                client_id=client_id,
                company_id=company_id,
                interview_date=normalized_date,
            )
            if existing:
                raise ValueError("A direct interview for this candidate, company, and datetime already exists")

            interview_record = InterviewRecord(
                candidate_id=candidate.id,
                client_id=client_id,
                company_id=company_id,
                interviewer_id=interviewer_id,
                interview_date=normalized_date,
                position=position.strip() if position else None,
                skills=self.normalize_skills(skills),
                notes=notes,
                rating=rating
            )

            candidate.is_direct_interview = True
            candidate.updated_at = datetime.utcnow()

            db.add(interview_record)
            db.add(candidate)
            db.flush()

            if log_activity:
                db.add(
                    ActivityLog(
                        client_id=client_id,
                        user_id=interviewer_id,
                        action_type="DIRECT_INTERVIEW",
                        entity_id=candidate.id,
                        details={
                            "company_id": str(company_id),
                            "interview_date": normalized_date.isoformat(),
                            "position": position,
                            "skills": self.normalize_skills(skills),
                            "rating": rating,
                        },
                    )
                )

            logger.info(
                "Interview record created",
                interview_id=str(interview_record.id),
                candidate_id=str(candidate.id),
                company_id=str(company_id),
                rating=rating
            )

            return interview_record

        except ValueError as e:
            logger.warning(
                "Invalid interview data",
                candidate_id=str(candidate.id),
                error=str(e)
            )
            raise
        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to record interview",
                candidate_id=str(candidate.id),
                error=str(e)
            )
            raise

    def update_interview(
        self,
        db: Session,
        interview: InterviewRecord,
        candidate: Candidate,
        editor_id: UUID,
        interview_date: Optional[datetime] = None,
        company_id: Optional[UUID] = None,
        position: Optional[str] = None,
        skills: Optional[List[str]] = None,
        notes: Optional[str] = None,
        rating: Optional[int] = None,
        log_activity: bool = False,
    ) -> InterviewRecord:
        """Update an existing direct interview while the candidate is still active."""
        if candidate.status != "ACTIVE":
            raise ValueError("Direct interview records can only be edited while the candidate is ACTIVE")

        if rating is not None and (rating < 1 or rating > 5):
            raise ValueError("Interview rating must be between 1 and 5")

        normalized_date = interview.interview_date
        if interview_date is not None:
            normalized_date = self.validate_interview_datetime(
                interview_date,
                candidate_created_at=candidate.created_at,
            )

        target_company_id = company_id or interview.company_id
        duplicate = self.find_duplicate_interview(
            db=db,
            candidate_id=candidate.id,
            client_id=interview.client_id,
            company_id=target_company_id,
            interview_date=normalized_date,
            exclude_interview_id=interview.id,
        )
        if duplicate:
            raise ValueError("A direct interview for this candidate, company, and datetime already exists")

        if interview_date is not None:
            interview.interview_date = normalized_date
        if company_id is not None:
            interview.company_id = company_id
        if position is not None:
            interview.position = position.strip() or None
        if skills is not None:
            interview.skills = self.normalize_skills(skills)
        interview.notes = notes
        interview.rating = rating
        interview.updated_at = datetime.utcnow()

        db.add(interview)
        db.flush()

        if log_activity:
            db.add(
                ActivityLog(
                    client_id=interview.client_id,
                    user_id=editor_id,
                    action_type="DIRECT_INTERVIEW_UPDATED",
                    entity_id=candidate.id,
                    details={
                        "interview_id": str(interview.id),
                        "company_id": str(interview.company_id),
                        "interview_date": interview.interview_date.isoformat(),
                        "position": interview.position,
                        "skills": interview.skills,
                        "rating": interview.rating,
                    },
                )
            )

        logger.info(
            "Interview record updated",
            interview_id=str(interview.id),
            candidate_id=str(candidate.id),
            company_id=str(interview.company_id),
        )
        return interview
    
    def get_interview_history(
        self,
        db: Session,
        candidate_id: UUID,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[InterviewRecord]:
        """Get interview history for a candidate.
        
        Args:
            db: Database session
            candidate_id: ID of candidate
            client_id: ID of client (tenant)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of interview records
        """
        try:
            interviews = (
                db.query(InterviewRecord)
                .filter(
                    InterviewRecord.candidate_id == candidate_id,
                    InterviewRecord.client_id == client_id,
                    InterviewRecord.deleted_at.is_(None),
                )
                .order_by(InterviewRecord.created_at.desc(), InterviewRecord.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            
            logger.info(
                "Interview history retrieved",
                candidate_id=str(candidate_id),
                count=len(interviews)
            )
            
            return interviews
            
        except Exception as e:
            logger.error(
                "Failed to retrieve interview history",
                candidate_id=str(candidate_id),
                error=str(e)
            )
            raise
    
    def get_interview_by_id(
        self,
        db: Session,
        interview_id: UUID,
        client_id: UUID
    ) -> Optional[InterviewRecord]:
        """Get a specific interview record by ID.
        
        Args:
            db: Database session
            interview_id: ID of interview record
            client_id: ID of client (tenant)
            
        Returns:
            Interview record or None if not found
        """
        try:
            interview = db.query(InterviewRecord).filter(
                InterviewRecord.id == interview_id,
                InterviewRecord.client_id == client_id,
                InterviewRecord.deleted_at.is_(None)
            ).first()
            
            return interview
            
        except Exception as e:
            logger.error(
                "Failed to retrieve interview",
                interview_id=str(interview_id),
                error=str(e)
            )
            raise
    
    def soft_delete_interview(
        self,
        db: Session,
        candidate: Candidate,
        interview_id: UUID,
        client_id: UUID,
        actor_id: Optional[UUID] = None,
        log_activity: bool = False,
    ) -> bool:
        """Soft delete an interview record (audit trail).
        
        Args:
            db: Database session
            interview_id: ID of interview record to delete
            client_id: ID of client (tenant)
            
        Returns:
            True if deleted, False if not found
        """
        try:
            if candidate.status != "ACTIVE":
                raise ValueError("Direct interview records can only be deleted while the candidate is ACTIVE")

            interview = db.query(InterviewRecord).filter(
                InterviewRecord.id == interview_id,
                InterviewRecord.client_id == client_id,
                InterviewRecord.deleted_at.is_(None)
            ).first()
            
            if not interview:
                return False
            
            interview.deleted_at = datetime.utcnow()
            interview.updated_at = datetime.utcnow()
            db.add(interview)

            remaining_interview = (
                db.query(InterviewRecord.id)
                .filter(
                    InterviewRecord.candidate_id == candidate.id,
                    InterviewRecord.client_id == client_id,
                    InterviewRecord.deleted_at.is_(None),
                    InterviewRecord.id != interview.id,
                )
                .first()
            )
            candidate.is_direct_interview = remaining_interview is not None
            candidate.updated_at = datetime.utcnow()
            db.add(candidate)

            if log_activity and actor_id is not None:
                db.add(
                    ActivityLog(
                        client_id=client_id,
                        user_id=actor_id,
                        action_type="DIRECT_INTERVIEW_DELETED",
                        entity_id=candidate.id,
                        details={
                            "interview_id": str(interview.id),
                            "company_id": str(interview.company_id),
                        },
                    )
                )

            db.flush()
            
            logger.info(
                "Interview record soft-deleted",
                interview_id=str(interview_id),
                candidate_id=str(interview.candidate_id),
                has_remaining_interviews=candidate.is_direct_interview,
            )
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to soft-delete interview",
                interview_id=str(interview_id),
                error=str(e)
            )
            raise
