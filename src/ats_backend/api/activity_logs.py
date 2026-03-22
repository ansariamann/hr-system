"""Activity Log API endpoints."""

from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client, require_roles
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.activity_log import ActivityLog
from ats_backend.schemas.activity_log import ActivityLogResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


@router.get("", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    limit: int = 100,
    skip: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get activity logs for the current client, ordered by newest first."""
    logs = (
        db.query(ActivityLog)
        .outerjoin(User, ActivityLog.user_id == User.id)
        .filter(ActivityLog.client_id == current_client.id)
        .order_by(desc(ActivityLog.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Map user_name for the response
    response_logs = []
    for log in logs:
        log_res = ActivityLogResponse.model_validate(log)
        if log.user:
            log_res.user_name = log.user.full_name or log.user.email
        response_logs.append(log_res)
        
    return response_logs


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
