"""Job posting API endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ats_backend.core.database import get_db
from ats_backend.core.error_handling import with_error_handling
from ats_backend.core.session_context import set_client_context
from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.models.job import Job
from ats_backend.schemas.job import JobCreate, JobUpdate, JobResponse
from ats_backend.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=List[JobResponse])
@with_error_handling(component="jobs_api")
def list_jobs(
    search: Optional[str] = None,
    company_name: Optional[str] = None,
    job_title: Optional[str] = None,
    field: Optional[str] = None,
    location: Optional[str] = None,
    min_experience: Optional[int] = Query(None, ge=0, le=60),
    max_experience: Optional[int] = Query(None, ge=0, le=60),
    min_salary_lpa: Optional[float] = Query(None, ge=0),
    max_salary_lpa: Optional[float] = Query(None, ge=0),
    sort: Optional[str] = Query(None, max_length=32),
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List jobs for current client with filters."""
    service = JobService()
    return service.list_jobs(
        db,
        search=search,
        company_name=company_name,
        job_title=job_title,
        field=field,
        location=location,
        min_experience=min_experience,
        max_experience=max_experience,
        min_salary_lpa=min_salary_lpa,
        max_salary_lpa=max_salary_lpa,
        sort=sort,
        skip=skip,
        limit=limit
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@with_error_handling(component="jobs_api")
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new job posting."""
    allowed_roles = {"hr_admin", "hr_user", "client_admin"}
    user_role = (current_user.role or "").lower()
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create jobs"
        )

    if payload.client_id:
        if user_role != "hr_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR admin can set client_id"
            )
        client_id = payload.client_id
    else:
        client_id = current_user.client_id

    set_client_context(db, client_id)

    job = Job(
        client_id=client_id,
        title=payload.title,
        company_name=payload.company_name,
        posting_date=payload.posting_date,
        requirements=payload.requirements,
        experience_required=payload.experience_required,
        salary_lpa=payload.salary_lpa,
        location=payload.location,
    )

    service = JobService()
    job = service.create_job(db, job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
@with_error_handling(component="jobs_api")
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get job by ID."""
    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobResponse)
@with_error_handling(component="jobs_api")
def update_job(
    job_id: UUID,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a job posting."""
    allowed_roles = {"hr_admin", "hr_user", "client_admin"}
    user_role = (current_user.role or "").lower()
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update jobs"
        )

    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    updates = payload.dict(exclude_unset=True)
    job = JobService.update_job(db, job, updates)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
@with_error_handling(component="jobs_api")
def delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a job posting."""
    allowed_roles = {"hr_admin", "hr_user", "client_admin"}
    user_role = (current_user.role or "").lower()
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete jobs"
        )

    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    JobService.delete_job(db, job)
    db.commit()
