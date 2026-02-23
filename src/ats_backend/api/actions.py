"""Client portal action endpoints — schedule interview, select, reject, feedback, left-company."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate
from ats_backend.models.fsm_transition_log import FSMTransitionLog, ActorType
from ats_backend.schemas.candidate import CandidateResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class ScheduleInterviewPayload(BaseModel):
    candidateId: str
    scheduledDate: Optional[str] = None
    interviewType: Optional[str] = None
    notes: Optional[str] = None
    roundNumber: Optional[int] = 1


class SelectPayload(BaseModel):
    candidateId: str
    notes: Optional[str] = None


class RejectPayload(BaseModel):
    candidateId: str
    reason: str = "Not selected"
    feedback: Optional[str] = None


class FeedbackPayload(BaseModel):
    candidateId: str
    roundNumber: Optional[int] = 1
    rating: Optional[int] = None          # 1-5
    recommendation: Optional[str] = None  # HIRE / NO_HIRE / MAYBE
    feedback: Optional[str] = None


class LeftCompanyPayload(BaseModel):
    candidateId: str
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_candidate(db: Session, candidate_id: str, client: Client) -> Candidate:
    """Fetch candidate and verify it belongs to the client."""
    try:
        uid = UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID format")

    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == uid, Candidate.client_id == client.id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


def _log_transition(
    db: Session,
    candidate: Candidate,
    new_status: str,
    actor: User,
    client: Client,
    reason: str,
    terminal: bool = False,
):
    """Update candidate status and write an FSMTransitionLog row."""
    old_status = candidate.status
    candidate.status = new_status
    candidate.updated_at = datetime.utcnow()

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
    candidate: Candidate,
    actor: User,
    client: Client,
    reason: str,
):
    """Write a log entry without changing candidate status (e.g. feedback)."""
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/schedule-interview", response_model=CandidateResponse)
async def schedule_interview(
    payload: ScheduleInterviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Schedule an interview for a candidate."""
    candidate = _get_candidate(db, payload.candidateId, current_client)

    reason_parts = [f"Interview scheduled"]
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
        db, candidate, "INTERVIEW_SCHEDULED",
        current_user, current_client, reason
    )

    logger.info(
        "Interview scheduled",
        candidate_id=str(candidate.id),
        client_id=str(current_client.id),
        user_id=str(current_user.id),
    )
    return candidate


@router.post("/select", response_model=CandidateResponse)
async def select_candidate(
    payload: SelectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Mark a candidate as selected."""
    candidate = _get_candidate(db, payload.candidateId, current_client)

    reason = "Candidate selected"
    if payload.notes:
        reason += f" | Notes: {payload.notes}"

    candidate = _log_transition(
        db, candidate, "SELECTED",
        current_user, current_client, reason
    )

    logger.info(
        "Candidate selected",
        candidate_id=str(candidate.id),
        client_id=str(current_client.id),
        user_id=str(current_user.id),
    )
    return candidate


@router.post("/reject", response_model=CandidateResponse)
async def reject_candidate(
    payload: RejectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Reject a candidate."""
    candidate = _get_candidate(db, payload.candidateId, current_client)

    reason = f"Rejected: {payload.reason}"
    if payload.feedback:
        reason += f" | Feedback: {payload.feedback}"

    candidate = _log_transition(
        db, candidate, "REJECTED",
        current_user, current_client, reason, terminal=True
    )

    logger.info(
        "Candidate rejected",
        candidate_id=str(candidate.id),
        client_id=str(current_client.id),
        user_id=str(current_user.id),
    )
    return candidate


@router.post("/submit-feedback", response_model=CandidateResponse)
async def submit_feedback(
    payload: FeedbackPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Submit interview feedback for a candidate (no status change)."""
    candidate = _get_candidate(db, payload.candidateId, current_client)

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

    logger.info(
        "Interview feedback submitted",
        candidate_id=str(candidate.id),
        client_id=str(current_client.id),
        user_id=str(current_user.id),
    )
    return candidate


@router.post("/left-company", response_model=CandidateResponse)
async def left_company(
    payload: LeftCompanyPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Mark a candidate as having left the company."""
    candidate = _get_candidate(db, payload.candidateId, current_client)

    reason = "Candidate left the company"
    if payload.reason:
        reason += f" | Reason: {payload.reason}"

    candidate = _log_transition(
        db, candidate, "LEFT_COMPANY",
        current_user, current_client, reason, terminal=True
    )

    logger.info(
        "Candidate marked as left company",
        candidate_id=str(candidate.id),
        client_id=str(current_client.id),
        user_id=str(current_user.id),
    )
    return candidate
