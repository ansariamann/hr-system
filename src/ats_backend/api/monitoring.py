"""API endpoints for task and system monitoring."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
import structlog

from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.workers.celery_app import task_monitor, celery_app

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed status of a specific task."""
    try:
        task_info = task_monitor.get_task_info(task_id)
        
        logger.info(
            "Task status retrieved",
            task_id=task_id,
            user_id=str(current_user.id),
            state=task_info.get("state")
        )
        
        return task_info
        
    except Exception as e:
        logger.error(
            "Failed to get task status",
            task_id=task_id,
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.get("/tasks/active")
async def get_active_tasks(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get information about currently active tasks."""
    try:
        active_tasks = task_monitor.get_active_tasks()
        
        logger.info(
            "Active tasks retrieved",
            user_id=str(current_user.id),
            total_active=active_tasks.get("total_active", 0)
        )
        
        return active_tasks
        
    except Exception as e:
        logger.error(
            "Failed to get active tasks",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active tasks: {str(e)}"
        )


@router.get("/workers/stats")
async def get_worker_stats(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get worker statistics and health information."""
    try:
        worker_stats = task_monitor.get_worker_stats()
        
        logger.info(
            "Worker stats retrieved",
            user_id=str(current_user.id),
            total_workers=worker_stats.get("total_workers", 0)
        )
        
        return worker_stats
        
    except Exception as e:
        logger.error(
            "Failed to get worker stats",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get worker stats: {str(e)}"
        )


@router.get("/queues")
async def get_queue_info(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get queue lengths and information."""
    try:
        queue_info = task_monitor.get_queue_lengths()
        
        logger.info(
            "Queue info retrieved",
            user_id=str(current_user.id),
            total_queued=queue_info.get("total_queued", 0)
        )
        
        return queue_info
        
    except Exception as e:
        logger.error(
            "Failed to get queue info",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue info: {str(e)}"
        )


@router.get("/system/health")
async def get_system_health(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive system health information."""
    try:
        # Get all monitoring data
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        # Determine system health
        healthy = True
        issues = []
        
        # Check if workers are available
        if worker_stats.get("total_workers", 0) == 0:
            healthy = False
            issues.append("No workers available")
        
        # Check for errors in monitoring data
        if "error" in worker_stats:
            healthy = False
            issues.append(f"Worker stats error: {worker_stats['error']}")
        
        if "error" in active_tasks:
            healthy = False
            issues.append(f"Active tasks error: {active_tasks['error']}")
        
        if "error" in queue_info:
            healthy = False
            issues.append(f"Queue info error: {queue_info['error']}")
        
        # Check queue backlog
        total_queued = queue_info.get("total_queued", 0)
        if total_queued > 100:  # Configurable threshold
            issues.append(f"High queue backlog: {total_queued} tasks")
        
        health_status = {
            "healthy": healthy,
            "status": "healthy" if healthy else "degraded",
            "issues": issues,
            "summary": {
                "workers": worker_stats.get("total_workers", 0),
                "active_tasks": active_tasks.get("total_active", 0),
                "queued_tasks": total_queued
            },
            "details": {
                "workers": worker_stats,
                "active_tasks": active_tasks,
                "queues": queue_info
            }
        }
        
        logger.info(
            "System health retrieved",
            user_id=str(current_user.id),
            healthy=healthy,
            issues_count=len(issues)
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Failed to get system health",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Cancel a running task."""
    try:
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        
        logger.info(
            "Task cancelled",
            task_id=task_id,
            user_id=str(current_user.id)
        )
        
        return {
            "success": True,
            "message": f"Task {task_id} has been cancelled",
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(
            "Failed to cancel task",
            task_id=task_id,
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.get("/stats/processing")
async def get_processing_stats(
    client_id: Optional[str] = Query(None, description="Client ID to get stats for"),
    days_back: int = Query(30, description="Number of days to look back"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get processing statistics."""
    try:
        from ats_backend.workers.email_tasks import get_processing_stats as get_stats_task
        
        # Use current user's client if not specified
        target_client_id = client_id or str(current_user.client_id)
        
        # Queue the stats task
        task = get_stats_task.delay(target_client_id, days_back)
        
        # Wait for result (since stats should be quick)
        result = task.get(timeout=30)
        
        logger.info(
            "Processing stats retrieved",
            user_id=str(current_user.id),
            client_id=target_client_id,
            days_back=days_back
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Failed to get processing stats",
            user_id=str(current_user.id),
            client_id=client_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get processing stats: {str(e)}"
        )


@router.post("/cleanup/files")
async def trigger_file_cleanup(
    days_old: int = Query(30, description="Files older than this many days will be cleaned"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Trigger file cleanup task."""
    try:
        from ats_backend.workers.email_tasks import cleanup_old_files
        
        # Queue the cleanup task
        task = cleanup_old_files.delay(days_old)
        
        logger.info(
            "File cleanup task queued",
            user_id=str(current_user.id),
            task_id=task.id,
            days_old=days_old
        )
        
        return {
            "success": True,
            "message": "File cleanup task has been queued",
            "task_id": task.id,
            "days_old": days_old
        }
        
    except Exception as e:
        logger.error(
            "Failed to trigger file cleanup",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger file cleanup: {str(e)}"
        )


@router.post("/cleanup/failed-jobs")
async def trigger_failed_jobs_cleanup(
    client_id: Optional[str] = Query(None, description="Client ID to clean jobs for"),
    max_age_hours: int = Query(24, description="Maximum age in hours for failed jobs to keep"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Trigger failed jobs cleanup task."""
    try:
        from ats_backend.workers.email_tasks import cleanup_failed_jobs
        
        # Use current user's client if not specified
        target_client_id = client_id or str(current_user.client_id)
        
        # Queue the cleanup task
        task = cleanup_failed_jobs.delay(target_client_id, max_age_hours)
        
        logger.info(
            "Failed jobs cleanup task queued",
            user_id=str(current_user.id),
            task_id=task.id,
            client_id=target_client_id,
            max_age_hours=max_age_hours
        )
        
        return {
            "success": True,
            "message": "Failed jobs cleanup task has been queued",
            "task_id": task.id,
            "client_id": target_client_id,
            "max_age_hours": max_age_hours
        }
        
    except Exception as e:
        logger.error(
            "Failed to trigger failed jobs cleanup",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger failed jobs cleanup: {str(e)}"
        )