"""Job posting service."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from ats_backend.models.job import Job


class JobService:
    """Service for job posting operations."""

    @staticmethod
    def create_job(db: Session, job: Job) -> Job:
        db.add(job)
        db.flush()
        db.refresh(job)
        return job

    @staticmethod
    def get_job(db: Session, job_id: UUID) -> Optional[Job]:
        return db.query(Job).filter(Job.id == job_id).first()

    @staticmethod
    def list_jobs(
        db: Session,
        search: Optional[str] = None,
        company_name: Optional[str] = None,
        job_title: Optional[str] = None,
        location: Optional[str] = None,
        min_experience: Optional[int] = None,
        max_experience: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Job]:
        query = db.query(Job)

        if search:
            like = f"%{search.strip()}%"
            query = query.filter(or_(Job.title.ilike(like), Job.company_name.ilike(like)))

        if company_name:
            query = query.filter(Job.company_name.ilike(f"%{company_name.strip()}%"))

        if job_title:
            query = query.filter(Job.title.ilike(f"%{job_title.strip()}%"))

        if location:
            query = query.filter(Job.location.ilike(f"%{location.strip()}%"))

        if min_experience is not None:
            query = query.filter(Job.experience_required >= min_experience)

        if max_experience is not None:
            query = query.filter(Job.experience_required <= max_experience)

        query = query.order_by(Job.posting_date.desc(), Job.created_at.desc())
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_job(db: Session, job: Job, updates: dict) -> Job:
        for key, value in updates.items():
            setattr(job, key, value)
        db.flush()
        db.refresh(job)
        return job

    @staticmethod
    def delete_job(db: Session, job: Job) -> None:
        db.delete(job)
        db.flush()
