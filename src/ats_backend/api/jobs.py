"""Job posting API endpoints."""

from typing import List, Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ats_backend.core.database import get_db
from ats_backend.core.error_handling import with_error_handling
from ats_backend.core.session_context import set_client_context, with_client_context
from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.job import Job
from ats_backend.models.activity_log import ActivityLog
from ats_backend.schemas.job import JobCreate, JobUpdate, JobResponse
from ats_backend.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=List[JobResponse])
@with_error_handling(component="jobs_api")
def list_jobs(
    client_id: Optional[UUID] = Query(None, description="Filter jobs by client (HR roles only)"),
    search: Optional[str] = None,
    company_name: Optional[str] = None,
    job_title: Optional[str] = None,
    field: Optional[str] = None,
    department: Optional[str] = None,
    employment_type: Optional[str] = None,
    job_status: Optional[str] = None,
    location: Optional[str] = None,
    min_experience: Optional[int] = Query(None, ge=0, le=60),
    max_experience: Optional[int] = Query(None, ge=0, le=60),
    min_salary_lpa: Optional[float] = Query(None, ge=0),
    max_salary_lpa: Optional[float] = Query(None, ge=0),
    sort: Optional[str] = Query(None, max_length=32),
    include_filled: bool = Query(False, description="Include non-vacant jobs in the response"),
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List jobs for current client with filters."""
    service = JobService()
    user_role = (current_user.role or "").lower()
    privileged_roles = {"hr_admin", "hr_recruiter"}
    requested_client_id = client_id

    if requested_client_id is not None:
        if user_role not in privileged_roles and requested_client_id != current_user.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to access jobs for this client"
            )
        client = db.query(Client).filter(Client.id == requested_client_id).first()
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    if user_role in privileged_roles:
        # HR roles can view all jobs unless they explicitly scope to one client.
        effective_client_id = requested_client_id
    else:
        effective_client_id = requested_client_id or current_user.client_id

    list_kwargs = {
        "db": db,
        "client_id": effective_client_id,
        "search": search,
        "company_name": company_name,
        "job_title": job_title,
        "field": field,
        "department": department,
        "employment_type": employment_type,
        "status": job_status,
        "location": location,
        "min_experience": min_experience,
        "max_experience": max_experience,
        "min_salary_lpa": min_salary_lpa,
        "max_salary_lpa": max_salary_lpa,
        "sort": sort,
        "include_filled": include_filled or user_role in privileged_roles,
        "skip": skip,
        "limit": limit,
    }

    if user_role in privileged_roles and effective_client_id is None:
        # RLS enforces one client context at a time, so aggregate client-scoped results.
        all_client_ids = [client.id for client in db.query(Client).all()]
        if not all_client_ids:
            return []

        per_client_kwargs = {
            **list_kwargs,
            "skip": 0,
            "limit": max(skip + limit, limit),
        }
        combined_jobs: List[Job] = []
        for tenant_client_id in all_client_ids:
            with with_client_context(db, tenant_client_id):
                combined_jobs.extend(
                    service.list_jobs(
                        **{
                            **per_client_kwargs,
                            "client_id": tenant_client_id,
                        }
                    )
                )

        sort_value = (sort or "").strip().lower() or "newest"
        if sort_value == "salary_desc":
            combined_jobs.sort(
                key=lambda job: (
                    job.salary_lpa is None,
                    -(float(job.salary_lpa) if job.salary_lpa is not None else 0.0),
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        elif sort_value == "salary_asc":
            combined_jobs.sort(
                key=lambda job: (
                    job.salary_lpa is None,
                    float(job.salary_lpa) if job.salary_lpa is not None else 0.0,
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        elif sort_value == "exp_desc":
            combined_jobs.sort(
                key=lambda job: (
                    job.experience_required is None,
                    -(job.experience_required if job.experience_required is not None else 0),
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        elif sort_value == "exp_asc":
            combined_jobs.sort(
                key=lambda job: (
                    job.experience_required is None,
                    job.experience_required if job.experience_required is not None else 0,
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        elif sort_value == "location_asc":
            combined_jobs.sort(
                key=lambda job: (
                    job.location is None,
                    (job.location or "").lower(),
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        elif sort_value == "company_asc":
            combined_jobs.sort(
                key=lambda job: (
                    (job.company_name or "").lower(),
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        else:
            combined_jobs.sort(
                key=lambda job: (
                    -(job.posting_date.toordinal() if job.posting_date else 0),
                    -(job.created_at.timestamp() if job.created_at else 0.0),
                )
            )
        return combined_jobs[skip: skip + limit]

    if (
        user_role in privileged_roles
        and effective_client_id is not None
        and current_user.client_id is not None
        and effective_client_id != current_user.client_id
    ):
        with with_client_context(db, effective_client_id):
            return service.list_jobs(**list_kwargs)

    return service.list_jobs(**list_kwargs)


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@with_error_handling(component="jobs_api")
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new job posting."""
    allowed_roles = {"hr_admin", "hr_recruiter", "client_admin"}
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

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    set_client_context(db, client_id)

    submitted_by_client = user_role == "client_admin"

    posting_date = date.today() if submitted_by_client else payload.posting_date

    job = Job(
        client_id=client_id,
        title=payload.title,
        company_name=client.name,
        posting_date=posting_date,
        closing_date=payload.closing_date,
        requirements=payload.requirements,
        department=payload.department,
        employment_type=payload.employment_type,
        experience_required=payload.experience_required,
        salary_lpa=payload.salary_lpa,
        location=payload.location,
        openings_count=payload.openings_count,
        status=payload.status,
        vacant=True,
        submitted_by_client=submitted_by_client,
    )

    service = JobService()
    job = service.create_job(db, job)
    
    activity_log = ActivityLog(
        client_id=client_id,
        user_id=current_user.id,
        action_type="JOB_CREATED",
        entity_id=job.id,
        details={
            "title": job.title,
            "company_name": job.company_name,
            "submitted_by_client": submitted_by_client,
            "source": "client_portal" if submitted_by_client else "hr_admin",
            "posting_date": job.posting_date.isoformat() if job.posting_date else None,
            "closing_date": job.closing_date.isoformat() if job.closing_date else None,
            "department": job.department,
            "employment_type": job.employment_type,
            "openings_count": job.openings_count,
            "status": job.status,
            "vacant": job.vacant,
        }
    )
    db.add(activity_log)
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
    allowed_roles = {"hr_admin", "hr_recruiter", "client_admin"}
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
    if "company_name" in updates:
        client = db.query(Client).filter(Client.id == job.client_id).first()
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
        updates["company_name"] = client.name
    previous_values = {
        "title": job.title,
        "company_name": job.company_name,
        "posting_date": job.posting_date.isoformat() if job.posting_date else None,
        "closing_date": job.closing_date.isoformat() if job.closing_date else None,
        "requirements": job.requirements,
        "department": job.department,
        "employment_type": job.employment_type,
        "experience_required": job.experience_required,
        "salary_lpa": float(job.salary_lpa) if job.salary_lpa is not None else None,
        "location": job.location,
        "openings_count": job.openings_count,
        "status": job.status,
        "vacant": job.vacant,
    }
    job = JobService.update_job(db, job, updates)
    updated_values = {
        "title": job.title,
        "company_name": job.company_name,
        "posting_date": job.posting_date.isoformat() if job.posting_date else None,
        "closing_date": job.closing_date.isoformat() if job.closing_date else None,
        "requirements": job.requirements,
        "department": job.department,
        "employment_type": job.employment_type,
        "experience_required": job.experience_required,
        "salary_lpa": float(job.salary_lpa) if job.salary_lpa is not None else None,
        "location": job.location,
        "openings_count": job.openings_count,
        "status": job.status,
        "vacant": job.vacant,
    }
    changed_fields = sorted(
        key for key, old_value in previous_values.items() if old_value != updated_values.get(key)
    )
    activity_log = ActivityLog(
        client_id=job.client_id,
        user_id=current_user.id,
        action_type="JOB_UPDATED",
        entity_id=job.id,
        details={
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "updated_values": updated_values,
        }
    )
    db.add(activity_log)
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
    """Delete a job posting.

    For client users, this is treated as a soft delete (close job) so HR retains visibility.
    """
    allowed_roles = {"hr_admin", "hr_recruiter", "client_admin"}
    user_role = (current_user.role or "").lower()
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete jobs"
        )

    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user_role == "client_admin":
        job = JobService.update_job(
            db,
            job,
            {
                "status": "CLOSED",
                "vacant": False,
                "closing_date": job.closing_date or date.today(),
            },
        )
        activity_log = ActivityLog(
            client_id=job.client_id,
            user_id=current_user.id,
            action_type="JOB_CLOSED_BY_CLIENT",
            entity_id=job_id,
            details={
                "job_id": str(job_id),
                "title": job.title,
                "company_name": job.company_name,
                "status": job.status,
                "vacant": job.vacant,
                "closing_date": job.closing_date.isoformat() if job.closing_date else None,
            },
        )
    else:
        JobService.delete_job(db, job)
        activity_log = ActivityLog(
            client_id=job.client_id,
            user_id=current_user.id,
            action_type="JOB_DELETED",
            entity_id=job_id,
            details={"job_id": str(job_id), "title": job.title, "company_name": job.company_name},
        )
    db.add(activity_log)
    db.commit()
