"""Candidate management API endpoints."""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, field_validator

import shutil
from pathlib import Path
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client, require_roles
from ats_backend.auth.models import User
from ats_backend.models.candidate import Candidate
from ats_backend.models.client import Client
from ats_backend.models.application import Application
from ats_backend.models.activity_log import ActivityLog
from ats_backend.services.candidate_service import CandidateService
from ats_backend.services.interview_service import InterviewService
from ats_backend.services.resume_job_service import ResumeJobService
from ats_backend.schemas.candidate import (
    CandidateCreate,
    CandidateUpdate,
    CandidateResponse
)
from ats_backend.schemas.resume_job import ResumeJobCreate

from ats_backend.resume.parser import ResumeParser
from ats_backend.core.config import settings
from ats_backend.core.logging import performance_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])

CLIENT_SCOPED_ROLES = {"client_user", "client_admin"}
HR_PRIVILEGED_ROLES = {"hr_admin", "hr_recruiter", "hr_user"}


def _is_client_scoped_user(user: User) -> bool:
    return (user.role or "").lower() in CLIENT_SCOPED_ROLES


def _is_hr_privileged_user(user: User) -> bool:
    return (user.role or "").lower() in HR_PRIVILEGED_ROLES


def _normalize_resume_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    resume_url = payload.get("resume_url")
    resume_file_path = payload.get("resume_file_path")

    if resume_url and not resume_file_path:
        payload["resume_file_path"] = resume_url
    if resume_file_path and not resume_url:
        payload["resume_url"] = resume_file_path

    return payload


def _infer_company_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    try:
        from ats_backend.services.candidate_service import infer_company
        return infer_company(payload.get("previous_employment"))
    except Exception:
        return None


def _resolve_candidate_for_client_access(
    db: Session,
    candidate_id: UUID,
    current_client: Client,
) -> Optional[Candidate]:
    """Resolve a candidate for client-facing actions.

    Prefer a direct candidate tenant match, but fall back to an active application
    under the current client for legacy records created with mismatched candidate
    ownership. This keeps existing client-portal workflows working while stricter
    validation prevents new inconsistent records.
    """
    candidate_service = CandidateService()
    candidate = candidate_service.get_candidate_by_id_for_client(
        db, candidate_id, current_client.id
    )
    if candidate:
        return candidate

    application = (
        db.query(Application)
        .filter(
            Application.client_id == current_client.id,
            Application.candidate_id == candidate_id,
            Application.deleted_at.is_(None),
        )
        .order_by(Application.created_at.desc())
        .first()
    )
    if not application or not application.candidate:
        return None

    logger.warning(
        "Resolved candidate via application fallback due to tenant mismatch",
        candidate_id=str(candidate_id),
        application_id=str(application.id),
        application_client_id=str(application.client_id),
        candidate_client_id=str(application.candidate.client_id),
    )
    return application.candidate


def _resolve_candidate_for_dashboard_access(
    db: Session,
    candidate_id: UUID,
    current_user: User,
    current_client: Client,
) -> Optional[Candidate]:
    candidate_service = CandidateService()

    if _is_hr_privileged_user(current_user):
        candidate = candidate_service.get_candidate_by_id(db, candidate_id)
        if candidate and candidate.client_id in {None, current_client.id}:
            return candidate

    return _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    request: Request,
    candidate_data: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Create a new candidate.
    
    Creates a new candidate record with audit logging and automatic
    client association based on the authenticated user's client.
    """
    try:
        with performance_logger.log_operation_time(
            "create_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            candidate_payload = _normalize_resume_fields(candidate_data.dict())
            if not candidate_payload.get("company"):
                inferred_company = _infer_company_from_payload(candidate_payload)
                if inferred_company:
                    candidate_payload["company"] = inferred_company
            if _is_client_scoped_user(current_user) and not candidate_payload.get("assigned_user_id"):
                candidate_payload["assigned_user_id"] = current_user.id
            candidate_data = CandidateCreate(**candidate_payload)

            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            candidate_service = CandidateService()
            candidate = candidate_service.create_candidate(
                db=db,
                client_id=current_client.id,
                candidate_data=candidate_data,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(
                "Candidate created via API",
                candidate_id=str(candidate.id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                name=candidate.name
            )
            
            db.commit()
            
            return candidate
            
    except ValueError as e:
        db.rollback()
        logger.warning(
            "Candidate creation failed - validation error",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "Candidate creation failed - internal error",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create candidate: {str(e)}"
        )


@router.post("/upload", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Upload resume and create candidate directly.
    
    Parses the uploaded resume and creates a candidate record.
    If parsing fails to extract a name, falls back to the filename.
    """
    temp_file_path = None
    keep_uploaded_file = False
    resume_job = None
    try:
        with performance_logger.log_operation_time(
            "upload_resume",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            # Create uploads directory if not exists
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            # Save file temporarily
            file_ext = Path(file.filename).suffix
            temp_file_name = f"upload_{uuid4()}{file_ext}"
            temp_file_path = upload_dir / temp_file_name
            
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Parse resume
            parser = ResumeParser()
            parse_result = parser.parse_file(temp_file_path, content_type=file.content_type)
            
            candidate_data_dict = {}
            candidate_remark = f"Resume uploaded: {file.filename}"
            
            if parse_result.success and parse_result.parsed_resume:
                parsed = parse_result.parsed_resume
                candidate_data_dict = parsed.to_candidate_data()
                
                # Append summary to remark if available
                if parsed.summary:
                     candidate_remark += f"\n\nSummary: {parsed.summary[:500]}..."
            
            # Prepare candidate creation data
            # Fallback for name if parsing failed needed
            name = candidate_data_dict.get("name")
            if not name:
                name = Path(file.filename).stem
                
            create_data = CandidateCreate(
                name=name,
                email=candidate_data_dict.get("email"),
                phone=candidate_data_dict.get("phone"),
                company=_infer_company_from_payload(candidate_data_dict),
                location=candidate_data_dict.get("location"),
                present_address=candidate_data_dict.get("present_address"),
                permanent_address=candidate_data_dict.get("permanent_address"),
                date_of_birth=candidate_data_dict.get("date_of_birth"),
                previous_employment=candidate_data_dict.get("previous_employment"),
                key_skill=candidate_data_dict.get("key_skill"),
                resume_file_path=f"/uploads/{temp_file_name}",
                resume_url=f"/uploads/{temp_file_name}",
                assigned_user_id=current_user.id if _is_client_scoped_user(current_user) else None,
                skills=candidate_data_dict.get("skills"),
                experience=candidate_data_dict.get("experience"),
                ctc_current=candidate_data_dict.get("ctc_current"),
                ctc_expected=candidate_data_dict.get("ctc_expected"),
                remark=candidate_remark,
                status="ACTIVE"
            )
            
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            resume_job_service = ResumeJobService()

            resume_job = resume_job_service.create_resume_job(
                db=db,
                client_id=current_client.id,
                job_data=ResumeJobCreate(
                    file_name=file.filename,
                    file_path=str(temp_file_path),
                    status="PROCESSING",
                ),
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.commit()
            
            # Create candidate
            candidate_service = CandidateService()
            candidate = candidate_service.create_candidate(
                db=db,
                client_id=current_client.id,
                candidate_data=create_data,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(
                "Candidate created via upload",
                candidate_id=str(candidate.id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                filename=file.filename
            )
            keep_uploaded_file = True
            
            # Record activity log
            activity_log = ActivityLog(
                client_id=current_client.id,
                user_id=current_user.id,
                action_type="CANDIDATE_UPLOADED",
                entity_id=candidate.id,
                details={"candidate_name": candidate.name, "filename": file.filename}
            )
            db.add(activity_log)
            db.commit()
            
            activity_log = ActivityLog(
                client_id=current_client.id,
                user_id=current_user.id,
                action_type="CANDIDATE_UPLOADED",
                entity_id=candidate.id,
                details={"name": candidate.name, "file_name": file.filename, "source": "resume_upload"}
            )
            db.add(activity_log)

            resume_job_service.update_job_status(
                db=db,
                job_id=resume_job.id,
                client_id=current_client.id,
                status="COMPLETED",
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.commit()
            
            return candidate
            
    except Exception as e:
        db.rollback()
        if resume_job is not None:
            try:
                resume_job_service = ResumeJobService()
                resume_job_service.update_job_status(
                    db=db,
                    job_id=resume_job.id,
                    client_id=current_client.id,
                    status="FAILED",
                    error_message=str(e),
                    user_id=current_user.id,
                )
                db.commit()
            except Exception:
                db.rollback()
        logger.error(
            "Resume upload failed",
            client_id=str(current_client.id),
            filename=file.filename,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}"
        )
    finally:
        # Cleanup temp file
        if temp_file_path and temp_file_path.exists() and not keep_uploaded_file:
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_file_path}: {e}")



@router.get("", response_model=List[CandidateResponse])
async def list_candidates(
    name_pattern: Optional[str] = Query(None, description="Search by name pattern"),
    skills: Optional[str] = Query(None, description="Search by skills (comma-separated)"),
    location: Optional[str] = Query(None, description="Search by location/city"),
    city: Optional[str] = Query(None, description="Deprecated: use location"),
    min_experience: Optional[int] = Query(None, description="Filter by minimum years of experience"),
    max_experience: Optional[int] = Query(None, description="Filter by maximum years of experience"),
    min_ctc_current: Optional[float] = Query(None, description="Filter by minimum current CTC"),
    max_ctc_current: Optional[float] = Query(None, description="Filter by maximum current CTC"),
    min_ctc_expected: Optional[float] = Query(None, description="Filter by minimum expected CTC"),
    max_ctc_expected: Optional[float] = Query(None, description="Filter by maximum expected CTC"),
    candidate_status: Optional[str] = Query(None, description="Filter by candidate status"),
    is_direct_interview: Optional[bool] = Query(None, description="Filter by direct interview flag"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """List candidates with optional filtering.
    
    Supports filtering by name pattern, skills, status, city, and max experience.
    Results are automatically filtered to the current client.
    """
    try:
        with performance_logger.log_operation_time(
            "list_candidates",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            candidate_service = CandidateService()
            
            # Parse skills if provided
            skills_list = None
            if skills:
                skills_list = [skill.strip() for skill in skills.split(",")]
            
            candidates = candidate_service.search_candidates(
                db=db,
                client_id=current_client.id,
                include_unassigned=_is_hr_privileged_user(current_user),
                name_pattern=name_pattern,
                skills=skills_list,
                location=location or city,
                min_experience=min_experience,
                max_experience=max_experience,
                min_ctc_current=min_ctc_current,
                max_ctc_current=max_ctc_current,
                min_ctc_expected=min_ctc_expected,
                max_ctc_expected=max_ctc_expected,
                status=candidate_status,
                is_direct_interview=is_direct_interview,
                assigned_user_id=current_user.id if _is_client_scoped_user(current_user) else None,
                skip=skip,
                limit=limit
            )
            
            logger.info(
                "Candidates listed via API",
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                count=len(candidates),
                filters={
                    "name_pattern": name_pattern,
                    "skills": skills,
                    "location": location or city,
                    "min_experience": min_experience,
                    "max_experience": max_experience,
                    "min_ctc_current": min_ctc_current,
                    "max_ctc_current": max_ctc_current,
                    "min_ctc_expected": min_ctc_expected,
                    "max_ctc_expected": max_ctc_expected,
                    "status": candidate_status,
                    "is_direct_interview": is_direct_interview,
                }
            )
            
            return candidates
            
    except Exception as e:
        logger.error(
            "Failed to list candidates",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list candidates: {str(e)}"
        )


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get a specific candidate by ID.
    
    Returns candidate details if the candidate belongs to the
    current client, otherwise returns 404.
    """
    try:
        with performance_logger.log_operation_time(
            "get_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate = _resolve_candidate_for_dashboard_access(
                db=db,
                candidate_id=candidate_id,
                current_user=current_user,
                current_client=current_client,
            )
            
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            if (
                _is_client_scoped_user(current_user)
                and candidate.client_id == current_client.id
                and candidate.assigned_user_id != current_user.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate retrieved via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return candidate
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get candidate",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate: {str(e)}"
        )


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: UUID,
    request: Request,
    candidate_data: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Update a candidate's information.
    
    Updates candidate data with audit logging. Only provided fields
    are updated, others remain unchanged.
    """
    try:
        with performance_logger.log_operation_time(
            "update_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            candidate_service = CandidateService()
            existing_candidate = _resolve_candidate_for_dashboard_access(
                db=db,
                candidate_id=candidate_id,
                current_user=current_user,
                current_client=current_client,
            )
            if not existing_candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            if _is_client_scoped_user(current_user) and existing_candidate.assigned_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not allowed to modify candidates not assigned to you"
                )

            candidate_payload = _normalize_resume_fields(candidate_data.dict(exclude_unset=True))
            if _is_client_scoped_user(current_user):
                # Client users cannot reassign candidates.
                candidate_payload.pop("assigned_user_id", None)
            candidate_data = CandidateUpdate(**candidate_payload)

            candidate = candidate_service.update_candidate(
                db=db,
                candidate_id=candidate_id,
                client_id=existing_candidate.client_id or current_client.id,
                candidate_data=candidate_data,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate updated via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return candidate
            
    except ValueError as e:
        logger.warning(
            "Candidate update failed - validation error",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update candidate",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update candidate: {str(e)}"
        )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Delete a candidate.
    
    Permanently deletes a candidate record with audit logging.
    This is a hard delete operation.
    """
    try:
        with performance_logger.log_operation_time(
            "delete_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            candidate_service = CandidateService()
            existing_candidate = _resolve_candidate_for_dashboard_access(
                db=db,
                candidate_id=candidate_id,
                current_user=current_user,
                current_client=current_client,
            )
            if not existing_candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            if _is_client_scoped_user(current_user) and existing_candidate.assigned_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not allowed to modify candidates not assigned to you"
                )

            deleted = candidate_service.delete_candidate(
                db=db,
                candidate_id=candidate_id,
                client_id=existing_candidate.client_id or current_client.id,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate deleted via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
    except ValueError as e:
        logger.warning(
            "Candidate deletion failed - validation error",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete candidate",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete candidate: {str(e)}"
        )


@router.get("/{candidate_id}/timeline")
async def get_candidate_timeline(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Return the FSM transition log for a candidate as a list of timeline events.

    Each event is shaped to match the frontend ApplicationTimeline type.
    """
    from ats_backend.models.fsm_transition_log import FSMTransitionLog

    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    logs = (
        db.query(FSMTransitionLog)
        .filter(
            FSMTransitionLog.candidate_id == candidate_id,
            FSMTransitionLog.client_id == current_client.id,
        )
        .order_by(FSMTransitionLog.created_at.asc())
        .all()
    )

    # Status → frontend state label mapping (mirrors api.ts statusToState)
    STATUS_TO_STATE = {
        "ACTIVE": "TO_REVIEW",
        "INACTIVE": "REJECTED",
        "HIRED": "JOINED",
        "LEFT_COMPANY": "LEFT_COMPANY",
        "REJECTED": "REJECTED",
        "INTERVIEW_SCHEDULED": "INTERVIEW_SCHEDULED",
        "SELECTED": "SELECTED",
    }

    timeline = []
    for log in logs:
        reason = log.reason or ""

        # ── Feedback events ──────────────────────────────────────────────────
        # Identified by reason starting with "interview_feedback"
        if reason.startswith("interview_feedback"):
            parts = dict(
                p.split("=", 1) for p in reason.split(" | ") if "=" in p
            )
            feedback_details = {
                "roundNumber": int(parts["round"]) if "round" in parts else None,
                "rating": int(parts["rating"]) if "rating" in parts else None,
                "recommendation": parts.get("recommendation"),
            }
            timeline.append({
                "id": str(log.id),
                "candidateId": str(log.candidate_id),
                "eventType": "feedback",
                "timestamp": log.created_at.isoformat(),
                "actor": "client" if log.actor_type == "USER" else "system",
                "note": parts.get("feedback", ""),
                "state": STATUS_TO_STATE.get(log.new_status, log.new_status),
                "oldStatus": None,
                "newStatus": None,
                "feedbackDetails": feedback_details,
                "interviewDetails": None,
            })

        # ── Interview-scheduled events ───────────────────────────────────────
        # Identified by new_status == INTERVIEW_SCHEDULED
        elif log.new_status == "INTERVIEW_SCHEDULED":
            # Parse pipe-delimited key: value pairs from reason
            kv = {}
            for part in reason.split(" | "):
                if ": " in part:
                    k, v = part.split(": ", 1)
                    kv[k.strip()] = v.strip()

            # Map interviewType → frontend mode value
            interview_type = kv.get("Type", "")
            mode_map = {
                "video": "video",
                "phone": "phone",
                "in_person": "in_person",
                "face-to-face": "in_person",
                "in person": "in_person",
            }
            mode = mode_map.get(interview_type.lower(), "video")

            interview_details = {
                "roundNumber": int(kv["Round"]) if "Round" in kv else 1,
                "mode": mode,
                "scheduledDate": kv.get("Date"),
                "interviewerName": None,
            }
            timeline.append({
                "id": str(log.id),
                "candidateId": str(log.candidate_id),
                "eventType": "interview_round",
                "timestamp": log.created_at.isoformat(),
                "actor": "client" if log.actor_type == "USER" else "system",
                "note": kv.get("Notes", ""),
                "state": "INTERVIEW_SCHEDULED",
                "oldStatus": log.old_status,
                "newStatus": log.new_status,
                "feedbackDetails": None,
                "interviewDetails": interview_details,
            })

        # ── Generic status-change events ─────────────────────────────────────
        else:
            timeline.append({
                "id": str(log.id),
                "candidateId": str(log.candidate_id),
                "eventType": "status_change",
                "timestamp": log.created_at.isoformat(),
                "actor": "client" if log.actor_type == "USER" else "system",
                "note": reason,
                "state": STATUS_TO_STATE.get(log.new_status, log.new_status),
                "oldStatus": log.old_status,
                "newStatus": log.new_status,
                "feedbackDetails": None,
                "interviewDetails": None,
            })

    logger.info(
        "Candidate timeline retrieved",
        candidate_id=str(candidate_id),
        client_id=str(current_client.id),
        events=len(timeline),
    )
    return timeline



@router.get("/{candidate_id}/duplicates", response_model=List[CandidateResponse])
async def find_candidate_duplicates(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Find potential duplicate candidates.
    
    Returns a list of candidates that might be duplicates of the
    specified candidate based on name, email, and phone matching.
    """
    try:
        with performance_logger.log_operation_time(
            "find_candidate_duplicates",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate_service = CandidateService()
            
            # First get the candidate to use for duplicate detection
            candidate = candidate_service.get_candidate_by_id_for_client(
                db, candidate_id, current_client.id
            )
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            if _is_client_scoped_user(current_user) and candidate.assigned_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            # Find potential duplicates
            duplicates = candidate_service.find_potential_duplicates(
                db=db,
                client_id=current_client.id,
                name=candidate.name,
                email=candidate.email,
                phone=candidate.phone
            )
            
            # Remove the original candidate from results
            duplicates = [dup for dup in duplicates if dup.id != candidate_id]
            
            logger.info(
                "Candidate duplicates found via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                duplicates_count=len(duplicates)
            )
            
            return duplicates
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to find candidate duplicates",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find candidate duplicates: {str(e)}"
        )


@router.get("/email/{email}", response_model=CandidateResponse)
async def get_candidate_by_email(
    email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get candidate by email address.
    
    Returns candidate with the specified email address within
    the current client's context.
    """
    try:
        with performance_logger.log_operation_time(
            "get_candidate_by_email",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            email=email
        ):
            candidate_service = CandidateService()
            if _is_hr_privileged_user(current_user):
                candidate = (
                    db.query(Candidate)
                    .filter(
                        Candidate.email == email,
                        or_(Candidate.client_id == current_client.id, Candidate.client_id.is_(None)),
                    )
                    .first()
                )
            else:
                candidate = candidate_service.get_candidate_by_email(
                    db, current_client.id, email
                )
            
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            if _is_client_scoped_user(current_user) and candidate.assigned_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate retrieved by email via API",
                candidate_id=str(candidate.id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                email=email
            )
            
            return candidate
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get candidate by email",
            email=email,
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate by email: {str(e)}"
        )


@router.get("/stats/summary")
async def get_candidate_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get candidate statistics for the current client.
    
    Returns summary statistics including total candidates,
    status breakdown, and other metrics.
    """
    try:
        with performance_logger.log_operation_time(
            "get_candidate_statistics",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            candidate_service = CandidateService()
            stats = candidate_service.get_candidate_statistics(
                db, current_client.id
            )
            
            logger.info(
                "Candidate statistics retrieved via API",
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                total_candidates=stats.get("total_candidates", 0)
            )
            
            return stats
            
    except Exception as e:
        logger.error(
            "Failed to get candidate statistics",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate statistics: {str(e)}"
        )


@router.get("/statistics")
async def get_candidate_statistics_alias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Alias for /stats/summary (frontend compatibility)."""
    return await get_candidate_statistics(
        db=db, current_user=current_user, current_client=current_client
    )


@router.get("/{candidate_id}/applications")
async def get_candidate_applications(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Get all applications for a specific candidate."""
    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    applications = (
        db.query(Application)
        .filter(
            Application.client_id == current_client.id,
            Application.candidate_id == candidate_id,
            Application.deleted_at.is_(None),
        )
        .order_by(Application.created_at.desc())
        .all()
    )

    logger.info(
        "Candidate applications retrieved",
        candidate_id=str(candidate_id),
        client_id=str(current_client.id),
        count=len(applications),
    )
    return applications


# ---------------------------------------------------------------------------
# Action Payloads & Endpoints
# ---------------------------------------------------------------------------

class ScheduleInterviewPayload(BaseModel):
    scheduledDate: Optional[str] = None
    interviewType: Optional[str] = None
    notes: Optional[str] = None
    roundNumber: Optional[int] = 1

class SelectPayload(BaseModel):
    notes: Optional[str] = None

class RejectPayload(BaseModel):
    reason: str = "Not selected"
    feedback: Optional[str] = None

class FeedbackPayload(BaseModel):
    roundNumber: Optional[int] = 1
    rating: Optional[int] = None          # 1-5
    recommendation: Optional[str] = None  # HIRE / NO_HIRE / MAYBE
    feedback: Optional[str] = None

class LeftCompanyPayload(BaseModel):
    reason: Optional[str] = None


class DirectInterviewPayload(BaseModel):
    """Payload for recording a direct interview with a candidate."""
    interview_date: datetime
    position: Optional[str] = None
    skills: Optional[List[str]] = None
    notes: Optional[str] = None
    rating: Optional[int] = None  # 1-5 scale
    company_id: UUID  # Target company for candidate placement
    
    @field_validator('interview_date')
    @classmethod
    def validate_interview_date(cls, v: datetime) -> datetime:
        """Validate interview date and normalize timezone-aware values to UTC."""
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        now = datetime.utcnow()
        min_date = now - timedelta(days=365 * 5)
        max_date = now + timedelta(days=365 * 5)
        if v < min_date or v > max_date:
            raise ValueError(f"Interview date must be between {min_date.date()} and {max_date.date()}")
        return v
    
    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        """Validate rating is between 1-5 if provided."""
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator('skills')
    @classmethod
    def validate_skills(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        normalized = [skill.strip() for skill in v if isinstance(skill, str) and skill.strip()]
        return normalized


class DirectSelectPayload(BaseModel):
    """Payload for selecting a candidate via direct interview and adding to company pool."""
    company_id: UUID
    notes: Optional[str] = None


class UpdateInterviewPayload(BaseModel):
    """Payload for updating an interview record."""
    interview_date: Optional[datetime] = None
    position: Optional[str] = None
    skills: Optional[List[str]] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    company_id: Optional[UUID] = None

    @field_validator('interview_date')
    @classmethod
    def validate_interview_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        now = datetime.utcnow()
        min_date = now - timedelta(days=365 * 5)
        max_date = now + timedelta(days=365 * 5)
        if v < min_date or v > max_date:
            raise ValueError(f"Interview date must be between {min_date.date()} and {max_date.date()}")
        return v

    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator('skills')
    @classmethod
    def validate_skills(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        normalized = [skill.strip() for skill in v if isinstance(skill, str) and skill.strip()]
        return normalized


class InterviewRecordResponse(BaseModel):
    """Response schema for interview records."""
    id: UUID
    candidate_id: UUID
    client_id: UUID
    company_id: UUID
    interviewer_id: UUID
    interview_date: datetime
    position: Optional[str] = None
    skills: Optional[List[str]] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _log_transition(
    db: Session,
    candidate,
    new_status: str,
    actor: User,
    client: Client,
    reason: str,
    terminal: bool = False,
    application_status: Optional[str] = None,
):
    from ats_backend.models.fsm_transition_log import FSMTransitionLog, ActorType
    old_status = candidate.status
    candidate.status = new_status
    candidate.updated_at = datetime.utcnow()

    if application_status:
        latest_application = (
            db.query(Application)
            .filter(
                Application.client_id == client.id,
                Application.candidate_id == candidate.id,
                Application.deleted_at.is_(None),
            )
            .order_by(Application.created_at.desc())
            .first()
        )
        if latest_application:
            latest_application.status = application_status
            latest_application.status_updated_at = datetime.utcnow()
            latest_application.updated_at = datetime.utcnow()
            if getattr(latest_application, "job_id", None):
                from ats_backend.services.job_service import JobService
                JobService.sync_job_vacancy(db, latest_application.job_id)

    log = FSMTransitionLog(
        candidate_id=candidate.id,
        old_status=old_status,
        new_status=new_status,
        actor_id=actor.id,
        actor_type=ActorType.USER,
        reason=reason,
        is_terminal=terminal,
        client_id=client.id,
    )
    db.add(log)
    db.commit()
    db.refresh(candidate)
    return candidate


def _log_event(
    db: Session,
    candidate,
    actor: User,
    client: Client,
    reason: str,
):
    from ats_backend.models.fsm_transition_log import FSMTransitionLog, ActorType
    log = FSMTransitionLog(
        candidate_id=candidate.id,
        old_status=candidate.status,
        new_status=candidate.status,
        actor_id=actor.id,
        actor_type=ActorType.USER,
        reason=reason,
        is_terminal=False,
        client_id=client.id,
    )
    db.add(log)
    db.commit()
    db.refresh(candidate)
    return candidate


def _get_next_interview_round(db: Session, candidate_id: UUID, client_id: UUID) -> int:
    from ats_backend.models.fsm_transition_log import FSMTransitionLog

    logs = (
        db.query(FSMTransitionLog)
        .filter(
            FSMTransitionLog.candidate_id == candidate_id,
            FSMTransitionLog.client_id == client_id,
            FSMTransitionLog.new_status == "INTERVIEW_SCHEDULED",
        )
        .order_by(FSMTransitionLog.created_at.asc())
        .all()
    )

    latest_round = 0
    for log in logs:
        reason = log.reason or ""
        for part in reason.split(" | "):
            if part.startswith("Round: "):
                try:
                    latest_round = max(latest_round, int(part.split(": ", 1)[1]))
                except ValueError:
                    continue

    return max(1, latest_round + 1)


@router.post("/{candidate_id}/schedule-interview", response_model=CandidateResponse)
async def schedule_interview(
    candidate_id: UUID,
    payload: ScheduleInterviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    expected_round = _get_next_interview_round(db, candidate.id, current_client.id)
    if expected_round > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview pipeline is limited to 6 rounds"
        )

    requested_round = payload.roundNumber or 1
    if requested_round != expected_round:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Next interview must be scheduled as round {expected_round}"
        )

    reason_parts = ["Interview scheduled"]
    if payload.scheduledDate:
        reason_parts.append(f"Date: {payload.scheduledDate}")
    if payload.interviewType:
        reason_parts.append(f"Type: {payload.interviewType}")
    if payload.roundNumber:
        reason_parts.append(f"Round: {payload.roundNumber}")
    if payload.notes:
        reason_parts.append(f"Notes: {payload.notes}")
    reason = " | ".join(reason_parts)

    candidate = _log_transition(
        db,
        candidate,
        "INTERVIEW_SCHEDULED",
        current_user,
        current_client,
        reason,
        application_status="INTERVIEW_SCHEDULED",
    )
    logger.info("Interview scheduled", candidate_id=str(candidate.id), client_id=str(current_client.id))
    return candidate


@router.post("/{candidate_id}/select", response_model=CandidateResponse)
async def select_candidate(
    candidate_id: UUID,
    payload: SelectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    reason = "Candidate selected"
    if payload.notes:
        reason += f" | Notes: {payload.notes}"

    candidate = _log_transition(
        db,
        candidate,
        "SELECTED",
        current_user,
        current_client,
        reason,
        application_status="HIRED",
    )
    logger.info("Candidate selected", candidate_id=str(candidate.id), client_id=str(current_client.id))
    # Auto-create a company employee record for the selected candidate
    try:
        from ats_backend.services.company_employee_service import CompanyEmployeeService

        # Determine role from latest application's job_title
        latest_app = (
            db.query(Application)
            .filter(
                Application.client_id == current_client.id,
                Application.candidate_id == candidate.id,
                Application.deleted_at.is_(None),
            )
            .order_by(Application.created_at.desc())
            .first()
        )
        role = latest_app.job_title if latest_app else None
        app_id = latest_app.id if latest_app else None

        CompanyEmployeeService.create_from_candidate(
            db,
            client_id=current_client.id,
            candidate_id=candidate.id,
            application_id=app_id,
            role=role,
        )
        db.commit()
    except Exception as emp_err:
        db.rollback()
        logger.warning(
            "Failed to auto-create company employee on select",
            candidate_id=str(candidate.id),
            error=str(emp_err),
        )

    return candidate


# ────────────────────────────────────────────────────────────────────────────
# DIRECT INTERVIEW ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.post("/{candidate_id}/direct-interview", response_model=InterviewRecordResponse)
async def record_direct_interview(
    candidate_id: UUID,
    payload: DirectInterviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    _: User = Depends(require_roles(['hr_admin'])),
):
    """Record a direct interview with a candidate.
    
    Only hr_admin users can conduct direct interviews. Captures interview details
    (date, notes, rating, interviewer) for a candidate without requiring a job posting.
    """
    try:
        with performance_logger.log_operation_time(
            "record_direct_interview",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_id_for_client(
                db, candidate_id, current_client.id
            )
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            company = db.query(Client).filter(
                Client.id == payload.company_id,
                Client.id == current_client.id
            ).first()
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid company_id or company does not belong to current client"
                )

            interview_service = InterviewService()
            interview_record = interview_service.record_interview(
                db=db,
                candidate=candidate,
                client_id=current_client.id,
                company_id=payload.company_id,
                interviewer_id=current_user.id,
                interview_date=payload.interview_date,
                position=payload.position,
                skills=payload.skills,
                notes=payload.notes,
                rating=payload.rating,
                log_activity=True,
            )
            db.commit()
            db.refresh(interview_record)

            logger.info(
                "Direct interview recorded",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                company_id=str(payload.company_id),
                rating=payload.rating
            )

            return InterviewRecordResponse.model_validate(interview_record)
    
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to record direct interview",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record direct interview: {str(e)}"
        )


@router.post("/{candidate_id}/direct-select", response_model=CandidateResponse)
async def select_candidate_directly(
    candidate_id: UUID,
    payload: DirectSelectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    _: User = Depends(require_roles(['hr_admin'])),
):
    """Select a candidate via direct interview and add to company's talent pool.
    
    Only hr_admin users can perform direct selection. Transitions candidate from
    ACTIVE to SELECTED status and associates them with the specified company.
    """
    try:
        with performance_logger.log_operation_time(
            "select_candidate_directly",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_id_for_client(
                db, candidate_id, current_client.id
            )
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            if candidate.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Candidate must be in ACTIVE status to perform direct selection"
                )
            if not candidate.is_direct_interview:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Candidate must have a direct interview recorded first"
                )

            company = db.query(Client).filter(
                Client.id == payload.company_id,
                Client.id == current_client.id
            ).first()
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid company_id or company does not belong to current client"
                )

            from ats_backend.models.interview_record import InterviewRecord
            latest_interview = (
                db.query(InterviewRecord)
                .filter(
                    InterviewRecord.candidate_id == candidate_id,
                    InterviewRecord.client_id == current_client.id,
                    InterviewRecord.company_id == payload.company_id,
                    InterviewRecord.deleted_at.is_(None),
                )
                .order_by(InterviewRecord.created_at.desc(), InterviewRecord.id.desc())
                .first()
            )
            if not latest_interview:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Candidate must have a direct interview for the selected company first"
                )

            from ats_backend.models.fsm_transition_log import FSMTransitionLog, ActorType

            old_status = candidate.status
            candidate.status = "SELECTED"
            candidate.updated_at = datetime.utcnow()

            transition_log = FSMTransitionLog(
                candidate_id=candidate.id,
                old_status=old_status,
                new_status="SELECTED",
                actor_id=current_user.id,
                actor_type=ActorType.USER,
                reason=f"Direct interview selection | Company: {str(payload.company_id)}" + (f" | Notes: {payload.notes}" if payload.notes else ""),
                is_terminal=False,
                client_id=current_client.id,
            )
            activity_log = ActivityLog(
                client_id=current_client.id,
                user_id=current_user.id,
                action_type="DIRECT_SELECTION",
                entity_id=candidate_id,
                details={
                    "company_id": str(payload.company_id),
                    "interview_id": str(latest_interview.id),
                    "notes": payload.notes,
                }
            )
            db.add(transition_log)
            db.add(activity_log)
            db.add(candidate)
            db.commit()
            db.refresh(candidate)

            try:
                from ats_backend.services.company_employee_service import CompanyEmployeeService

                CompanyEmployeeService.create_from_candidate(
                    db,
                    client_id=current_client.id,
                    candidate_id=candidate.id,
                    role=latest_interview.position,
                )
                db.commit()
            except Exception as emp_err:
                db.rollback()
                logger.warning(
                    "Failed to auto-create company employee on direct select",
                    candidate_id=str(candidate_id),
                    client_id=str(current_client.id),
                    error=str(emp_err),
                )

            logger.info(
                "Candidate selected via direct interview",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                company_id=str(payload.company_id)
            )

            return candidate
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to select candidate directly",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select candidate directly: {str(e)}"
        )


@router.get("/{candidate_id}/interview-history", response_model=List[InterviewRecordResponse])
async def get_interview_history(
    candidate_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get interview history for a candidate.
    
    Returns all interview records associated with a candidate, paginated with consistent ordering.
    Only hr_admin users can view all interviews; others can only view if assigned to candidate.
    """
    try:
        with performance_logger.log_operation_time(
            "get_interview_history",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_id_for_client(
                db, candidate_id, current_client.id
            )
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            # Check access control
            is_admin = (current_user.role or "").lower() == "hr_admin"
            if not is_admin and candidate.assigned_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not allowed to view interview history for this candidate"
                )
            
            interview_service = InterviewService()
            interviews = interview_service.get_interview_history(
                db=db,
                candidate_id=candidate_id,
                client_id=current_client.id,
                skip=skip,
                limit=limit,
            )
            
            logger.info(
                "Interview history retrieved",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                count=len(interviews)
            )
            
            return [InterviewRecordResponse.model_validate(interview) for interview in interviews]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get interview history",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get interview history: {str(e)}"
        )


@router.patch("/{candidate_id}/interview-history/{interview_id}", response_model=InterviewRecordResponse)
async def update_interview_record(
    candidate_id: UUID,
    interview_id: UUID,
    payload: UpdateInterviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    _: User = Depends(require_roles(['hr_admin'])),
):
    """Update a direct interview record while the candidate is still active."""
    try:
        with performance_logger.log_operation_time(
            "update_interview_record",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id),
            interview_id=str(interview_id),
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_id_for_client(
                db, candidate_id, current_client.id
            )
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            interview_service = InterviewService()
            interview = interview_service.get_interview_by_id(
                db=db,
                interview_id=interview_id,
                client_id=current_client.id,
            )
            if not interview or interview.candidate_id != candidate_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Interview record not found"
                )

            if payload.company_id is not None:
                company = db.query(Client).filter(
                    Client.id == payload.company_id,
                    Client.id == current_client.id
                ).first()
                if not company:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid company_id or company does not belong to current client"
                    )

            interview = interview_service.update_interview(
                db=db,
                interview=interview,
                candidate=candidate,
                editor_id=current_user.id,
                interview_date=payload.interview_date,
                company_id=payload.company_id,
                position=payload.position,
                skills=payload.skills,
                notes=payload.notes,
                rating=payload.rating,
                log_activity=True,
            )
            db.commit()
            db.refresh(interview)
            return InterviewRecordResponse.model_validate(interview)
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to update interview record",
            candidate_id=str(candidate_id),
            interview_id=str(interview_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update interview record: {str(e)}"
        )


@router.delete("/{candidate_id}/interview-history/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_record(
    candidate_id: UUID,
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    _: User = Depends(require_roles(['hr_admin'])),
):
    """Soft-delete a direct interview record while the candidate is still active."""
    try:
        with performance_logger.log_operation_time(
            "delete_interview_record",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id),
            interview_id=str(interview_id),
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_id_for_client(
                db, candidate_id, current_client.id
            )
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )

            interview_service = InterviewService()
            interview = interview_service.get_interview_by_id(
                db=db,
                interview_id=interview_id,
                client_id=current_client.id,
            )
            if not interview or interview.candidate_id != candidate_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Interview record not found"
                )

            deleted = interview_service.soft_delete_interview(
                db=db,
                candidate=candidate,
                interview_id=interview_id,
                client_id=current_client.id,
                actor_id=current_user.id,
                log_activity=True,
            )
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Interview record not found"
                )
            db.commit()
            return None
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to delete interview record",
            candidate_id=str(candidate_id),
            interview_id=str(interview_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete interview record: {str(e)}"
        )


@router.get("/direct-interview/stats")
async def get_direct_interview_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    _: User = Depends(require_roles(['hr_admin'])),
):
    """Return direct interview workflow counts."""
    total_pending = db.query(func.count()).select_from(Candidate).filter(
        Candidate.client_id == current_client.id,
        Candidate.status == "ACTIVE",
        Candidate.is_direct_interview.is_(False),
    ).scalar()
    total_interviewed = db.query(func.count()).select_from(Candidate).filter(
        Candidate.client_id == current_client.id,
        Candidate.status == "ACTIVE",
        Candidate.is_direct_interview.is_(True),
    ).scalar()
    total_selected = db.query(func.count()).select_from(Candidate).filter(
        Candidate.client_id == current_client.id,
        Candidate.status == "SELECTED",
    ).scalar()

    return {
        "pending": total_pending or 0,
        "interviewed": total_interviewed or 0,
        "selected": total_selected or 0,
    }


@router.post("/{candidate_id}/reject", response_model=CandidateResponse)
async def reject_candidate(
    candidate_id: UUID,
    payload: RejectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    reason = f"Rejected: {payload.reason}"
    if payload.feedback:
        reason += f" | Feedback: {payload.feedback}"

    candidate = _log_transition(
        db,
        candidate,
        "REJECTED",
        current_user,
        current_client,
        reason,
        terminal=True,
        application_status="REJECTED",
    )
    logger.info("Candidate rejected", candidate_id=str(candidate.id), client_id=str(current_client.id))
    return candidate


@router.post("/{candidate_id}/submit-feedback", response_model=CandidateResponse)
async def submit_feedback(
    candidate_id: UUID,
    payload: FeedbackPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    reason_parts = ["interview_feedback"]
    if payload.roundNumber:
        reason_parts.append(f"round={payload.roundNumber}")
    if payload.rating is not None:
        reason_parts.append(f"rating={payload.rating}")
    if payload.recommendation:
        reason_parts.append(f"recommendation={payload.recommendation}")
    if payload.feedback:
        reason_parts.append(f"feedback={payload.feedback}")
    reason = " | ".join(reason_parts)

    candidate = _log_event(db, candidate, current_user, current_client, reason)
    logger.info("Interview feedback submitted", candidate_id=str(candidate.id), client_id=str(current_client.id))
    return candidate


@router.post("/{candidate_id}/left-company", response_model=CandidateResponse)
async def left_company(
    candidate_id: UUID,
    payload: LeftCompanyPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    candidate = _resolve_candidate_for_client_access(
        db=db,
        candidate_id=candidate_id,
        current_client=current_client,
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    reason = "Candidate left the company"
    if payload.reason:
        reason += f" | Reason: {payload.reason}"

    candidate = _log_transition(
        db,
        candidate,
        "LEFT_COMPANY",
        current_user,
        current_client,
        reason,
        terminal=True,
        application_status="WITHDRAWN",
    )
    logger.info("Candidate left company", candidate_id=str(candidate.id), client_id=str(current_client.id))
    return candidate


@router.get("/{candidate_id}/applications")
async def get_candidate_applications(
    candidate_id: UUID,
    include_deleted: bool = Query(False, description="Include soft-deleted applications"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    from ats_backend.services.application_service import ApplicationService
    application_service = ApplicationService()
    applications = application_service.get_applications_by_candidate(
        db=db,
        client_id=current_client.id,
        candidate_id=candidate_id,
        include_deleted=include_deleted
    )
    return applications
