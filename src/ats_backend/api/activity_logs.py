"""Activity Log API endpoints."""

from typing import List, Dict, Any, Tuple
from datetime import date, datetime, time, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client, require_roles
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.activity_log import ActivityLog
from ats_backend.core.session_context import with_client_context
from ats_backend.schemas.activity_log import ActivityLogResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])
HR_PRIVILEGED_ROLES = {"hr_admin", "hr_recruiter", "hr_user"}


class ActivityTrackRequest(BaseModel):
    """Payload for recording ad-hoc dashboard activity."""

    action_type: str = Field(..., min_length=1, max_length=50)
    entity_id: UUID | None = None
    details: Dict[str, Any] | None = None


@router.get("", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    limit: int = 100,
    skip: int = 0,
    client_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get activity logs for the current client, ordered by newest first."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date",
        )

    def _query_logs_for_client(
        target_client_id: UUID,
        local_skip: int,
        local_limit: int,
    ) -> List[Tuple[ActivityLog, str | None, str | None]]:
        query = (
            db.query(ActivityLog, User.full_name, User.email)
            .outerjoin(User, ActivityLog.user_id == User.id)
            .filter(ActivityLog.client_id == target_client_id)
        )
        if start_date:
            query = query.filter(
                ActivityLog.created_at >= datetime.combine(start_date, time.min)
            )
        if end_date:
            query = query.filter(
                ActivityLog.created_at <= datetime.combine(end_date, time.max)
            )
        return (
            query
            .order_by(desc(ActivityLog.created_at), desc(ActivityLog.id))
            .offset(local_skip)
            .limit(local_limit)
            .all()
        )

    user_role = (current_user.role or "").strip().lower()
    is_hr_privileged = user_role in HR_PRIVILEGED_ROLES
    rows: List[Tuple[ActivityLog, str | None, str | None]]

    if not is_hr_privileged:
        if client_id is not None and client_id != current_client.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access activity logs for another client",
            )
        effective_client_id = client_id or current_client.id
        rows = _query_logs_for_client(effective_client_id, skip, limit)
    else:
        if client_id is not None:
            with with_client_context(db, client_id):
                rows = _query_logs_for_client(client_id, skip, limit)
        else:
            all_client_ids = [cid for (cid,) in db.query(Client.id).all()]
            if not all_client_ids:
                return []

            per_client_limit = max(skip + limit, limit)
            combined_rows: List[Tuple[ActivityLog, str | None, str | None]] = []
            for tenant_client_id in all_client_ids:
                with with_client_context(db, tenant_client_id):
                    combined_rows.extend(
                        _query_logs_for_client(tenant_client_id, 0, per_client_limit)
                    )

            combined_rows.sort(
                key=lambda row: (row[0].created_at, str(row[0].id)),
                reverse=True,
            )
            rows = combined_rows[skip: skip + limit]

    response_logs: List[ActivityLogResponse] = []
    for log, full_name, email in rows:
        log_res = ActivityLogResponse.model_validate(log)
        log_res.user_name = full_name or email
        response_logs.append(log_res)
    return response_logs


@router.post("/track", response_model=ActivityLogResponse, status_code=status.HTTP_201_CREATED)
async def track_activity(
    payload: ActivityTrackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Record a user activity event for the authenticated client."""
    try:
        log = ActivityLog(
            client_id=current_client.id,
            user_id=current_user.id,
            action_type=payload.action_type,
            entity_id=payload.entity_id,
            details=payload.details or {},
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        response = ActivityLogResponse.model_validate(log)
        response.user_name = current_user.full_name or current_user.email
        return response
    except Exception as exc:
        db.rollback()
        logger.error(
            "Failed to track activity",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            action_type=payload.action_type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track activity",
        )


@router.delete("/cleanup", status_code=status.HTTP_204_NO_CONTENT)
async def cleanup_old_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    _: User = Depends(require_roles(['hr_admin']))
):
    """Delete activity logs older than 1 year."""

    try:
        one_year_ago = datetime.utcnow() - timedelta(days=365)
        
        deleted_count = db.query(ActivityLog).filter(
            ActivityLog.client_id == current_client.id,
            ActivityLog.created_at < one_year_ago
        ).delete()
        
        db.commit()
        logger.info(
            "Cleaned up old activity logs",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            deleted_count=deleted_count
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to clean up activity logs",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clean up logs: {str(e)}"
        )
