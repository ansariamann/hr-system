"""Application management API endpoints."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session, joinedload
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User
from ats_backend.models.application import Application
from ats_backend.models.client import Client
from ats_backend.models.activity_log import ActivityLog
from ats_backend.services.application_service import ApplicationService
from ats_backend.services.client_service import ClientService
from ats_backend.core.session_context import with_client_context
from ats_backend.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse
)
from ats_backend.core.logging import performance_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])

HR_PRIVILEGED_ROLES = {"hr_admin", "hr_recruiter", "hr_user"}


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    request: Request,
    application_data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Create a new application.
    
    Creates a new application record with audit logging and automatic
    client association based on the authenticated user's client.
    """
    try:
        with performance_logger.log_operation_time(
            "create_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            application_service = ApplicationService()
            user_role = (current_user.role or "").strip().lower()
            requested_client_id = application_data.client_id or current_client.id

            if user_role not in HR_PRIVILEGED_ROLES and requested_client_id != current_client.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Applications can only be created for the authenticated client"
                )

            target_client = ClientService.get_client_by_id(db, requested_client_id)
            if not target_client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target client not found"
                )

            with with_client_context(db, target_client.id):
                application = application_service.create_application(
                    db=db,
                    client_id=target_client.id,
                    application_data=application_data,
                    user_id=current_user.id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            logger.info(
                "Application created via API",
                application_id=str(application.id),
                client_id=str(target_client.id),
                user_id=str(current_user.id),
                candidate_id=str(application.candidate_id),
                status=application.status
            )
            
            db.commit()
            
            return application
            
    except ValueError as e:
        db.rollback()
        logger.warning(
            "Application creation failed - validation error",
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
            "Application creation failed - internal error",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application: {str(e)}"
        )


@router.get("", response_model=List[ApplicationResponse])
async def list_applications(
    application_status: Optional[str] = Query(None, description="Filter by application status"),
    candidate_id: Optional[UUID] = Query(None, description="Filter by candidate ID"),
    client_id: Optional[UUID] = Query(None, description="Filter by client ID"),
    flagged_only: bool = Query(False, description="Show only flagged applications"),
    include_deleted: bool = Query(False, description="Include soft-deleted applications"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """List applications with optional filtering.
    
    Supports filtering by status, flagged status, and soft-deleted status.
    Results are automatically filtered to the current client.
    """
    try:
        with performance_logger.log_operation_time(
            "list_applications",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            application_service = ApplicationService()
            user_role = (current_user.role or "").strip().lower()
            is_hr_privileged = user_role in HR_PRIVILEGED_ROLES
            
            if is_hr_privileged:
                query = db.query(Application).options(
                    joinedload(Application.candidate),
                    joinedload(Application.client),
                )

                if client_id:
                    query = query.filter(Application.client_id == client_id)
                if candidate_id:
                    query = query.filter(Application.candidate_id == candidate_id)
                if application_status:
                    query = query.filter(Application.status == application_status)
                if flagged_only:
                    query = query.filter(Application.flagged_for_review.is_(True))
                if not include_deleted:
                    query = query.filter(Application.deleted_at.is_(None))

                applications = (
                    query
                    .order_by(Application.application_date.desc(), Application.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                    .all()
                )
            else:
                if client_id and client_id != current_client.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not allowed to access applications for another client"
                    )

                if flagged_only:
                    applications = application_service.get_flagged_applications(
                        db=db,
                        client_id=current_client.id,
                        skip=skip,
                        limit=limit
                    )
                elif application_status:
                    applications = application_service.get_applications_by_status(
                        db=db,
                        client_id=current_client.id,
                        status=application_status,
                        skip=skip,
                        limit=limit,
                        include_deleted=include_deleted
                    )
                elif include_deleted or candidate_id:
                    query = db.query(Application).options(
                        joinedload(Application.candidate),
                        joinedload(Application.client),
                    ).filter(Application.client_id == current_client.id)

                    if candidate_id:
                        query = query.filter(Application.candidate_id == candidate_id)
                    if not include_deleted:
                        query = query.filter(Application.deleted_at.is_(None))

                    applications = (
                        query
                        .order_by(Application.application_date.desc(), Application.created_at.desc())
                        .offset(skip)
                        .limit(limit)
                        .all()
                    )
                else:
                    applications = application_service.get_active_applications(
                        db=db,
                        client_id=current_client.id,
                        skip=skip,
                        limit=limit
                    )

            logger.info(
                "Applications listed via API",
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                count=len(applications),
                filters={
                    "status": application_status,
                    "candidate_id": str(candidate_id) if candidate_id else None,
                    "client_id": str(client_id) if client_id else None,
                    "flagged_only": flagged_only,
                    "include_deleted": include_deleted
                }
            )
            
            return applications
            
    except Exception as e:
        logger.error(
            "Failed to list applications",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list applications: {str(e)}"
        )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get a specific application by ID.
    
    Returns application details if the application belongs to the
    current client, otherwise returns 404.
    """
    try:
        with performance_logger.log_operation_time(
            "get_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            application_service = ApplicationService()
            application = application_service.get_application_by_id(db, application_id)
            
            if not application:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            # Verify application belongs to current client
            if application.client_id != current_client.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            logger.info(
                "Application retrieved via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return application
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get application",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get application: {str(e)}"
        )


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: UUID,
    request: Request,
    application_data: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Update an application's information.
    
    Updates application data with audit logging. Only provided fields
    are updated, others remain unchanged.
    """
    try:
        with performance_logger.log_operation_time(
            "update_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            application_service = ApplicationService()
            application = application_service.update_application(
                db=db,
                application_id=application_id,
                client_id=current_client.id,
                application_data=application_data,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not application:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            logger.info(
                "Application updated via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return application
            
    except ValueError as e:
        logger.warning(
            "Application update failed - validation error",
            application_id=str(application_id),
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
            "Failed to update application",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application: {str(e)}"
        )


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_application(
    application_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Soft delete an application.
    
    Marks an application as deleted while preserving historical data.
    This implements the soft delete requirement from the specifications.
    """
    try:
        with performance_logger.log_operation_time(
            "soft_delete_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            application_service = ApplicationService()
            deleted = application_service.soft_delete_application(
                db=db,
                application_id=application_id,
                client_id=current_client.id,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            logger.info(
                "Application soft deleted via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
    except ValueError as e:
        logger.warning(
            "Application soft deletion failed - validation error",
            application_id=str(application_id),
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
            "Failed to soft delete application",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to soft delete application: {str(e)}"
        )


@router.post("/{application_id}/restore", response_model=ApplicationResponse)
async def restore_application(
    application_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Restore a soft-deleted application.
    
    Restores a previously soft-deleted application back to active status.
    """
    try:
        with performance_logger.log_operation_time(
            "restore_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            application_service = ApplicationService()
            restored = application_service.restore_application(
                db=db,
                application_id=application_id,
                client_id=current_client.id,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not restored:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found or not deleted"
                )
            
            # Get the restored application to return
            application = application_service.get_application_by_id(db, application_id)
            
            logger.info(
                "Application restored via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return application
            
    except ValueError as e:
        logger.warning(
            "Application restoration failed - validation error",
            application_id=str(application_id),
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
            "Failed to restore application",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore application: {str(e)}"
        )


@router.post("/{application_id}/flag")
async def flag_application(
    application_id: UUID,
    flag_reason: str = Query(..., description="Reason for flagging the application"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Flag an application for manual review.
    
    Flags an application for manual review with a specified reason.
    This is used by the duplicate detection system and manual processes.
    """
    try:
        with performance_logger.log_operation_time(
            "flag_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            application_service = ApplicationService()
            
            # First verify the application exists and belongs to client
            application = application_service.get_application_by_id(db, application_id)
            if not application or application.client_id != current_client.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            flagged = application_service.flag_application(
                db=db,
                application_id=application_id,
                flag_reason=flag_reason,
                user_id=current_user.id
            )
            
            if not flagged:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            logger.info(
                "Application flagged via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                flag_reason=flag_reason
            )

            db.add(
                ActivityLog(
                    client_id=current_client.id,
                    user_id=current_user.id,
                    action_type="APPLICATION_FLAGGED",
                    entity_id=application_id,
                    details={"flag_reason": flag_reason},
                )
            )
            db.commit()
            
            return {
                "success": True,
                "message": "Application flagged for review",
                "application_id": str(application_id),
                "flag_reason": flag_reason
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to flag application",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flag application: {str(e)}"
        )


@router.post("/{application_id}/unflag")
async def unflag_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Remove flag from an application.
    
    Removes the flag from an application, allowing normal workflow progression.
    """
    try:
        with performance_logger.log_operation_time(
            "unflag_application",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            application_service = ApplicationService()
            
            # First verify the application exists and belongs to client
            application = application_service.get_application_by_id(db, application_id)
            if not application or application.client_id != current_client.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            unflagged = application_service.unflag_application(
                db=db,
                application_id=application_id
            )
            
            if not unflagged:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            logger.info(
                "Application unflagged via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )

            db.add(
                ActivityLog(
                    client_id=current_client.id,
                    user_id=current_user.id,
                    action_type="APPLICATION_UNFLAGGED",
                    entity_id=application_id,
                    details={},
                )
            )
            db.commit()
            
            return {
                "success": True,
                "message": "Application flag removed",
                "application_id": str(application_id)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to unflag application",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unflag application: {str(e)}"
        )


@router.put("/{application_id}/status")
async def update_application_status(
    application_id: UUID,
    new_status: str = Query(..., description="New status for the application"),
    force_update: bool = Query(False, description="Force update even if workflow progression is blocked"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Update application status with workflow progression controls.
    
    Updates application status while checking workflow progression rules.
    Flagged applications may be blocked from certain status changes unless forced.
    """
    try:
        with performance_logger.log_operation_time(
            "update_application_status",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent") if request else None
            
            application_service = ApplicationService()
            application = application_service.update_application_status(
                db=db,
                application_id=application_id,
                new_status=new_status,
                client_id=current_client.id,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                force_update=force_update
            )
            
            if not application:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            logger.info(
                "Application status updated via API",
                application_id=str(application_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                new_status=new_status,
                force_update=force_update
            )
            
            return application
            
    except ValueError as e:
        logger.warning(
            "Application status update failed - validation/workflow error",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            new_status=new_status,
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
            "Failed to update application status",
            application_id=str(application_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            new_status=new_status,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}"
        )





@router.get("/stats/summary")
async def get_application_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get application statistics for the current client.
    
    Returns summary statistics including total applications,
    status breakdown, and other metrics.
    """
    try:
        with performance_logger.log_operation_time(
            "get_application_statistics",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            application_service = ApplicationService()
            stats = application_service.get_application_statistics(
                db, current_client.id
            )
            
            logger.info(
                "Application statistics retrieved via API",
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                total_applications=stats.get("total_applications", 0)
            )
            
            return stats
            
    except Exception as e:
        logger.error(
            "Failed to get application statistics",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get application statistics: {str(e)}"
        )


@router.get("/statistics")
async def get_application_statistics_alias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Alias for /stats/summary (frontend compatibility)."""
    return await get_application_statistics(
        db=db, current_user=current_user, current_client=current_client
    )
