"""API endpoints for task and system monitoring."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from uuid import UUID
from datetime import datetime, timedelta
import structlog

from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.workers.celery_app import task_monitor, celery_app
from ats_backend.core.health import health_checker
from ats_backend.core.metrics import metrics_collector
from ats_backend.core.logging import performance_logger, system_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def comprehensive_health_check(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive system health information."""
    try:
        with performance_logger.log_operation_time(
            "comprehensive_health_check",
            user_id=str(current_user.id)
        ):
            health_report = await health_checker.run_all_checks()
        
        logger.info(
            "Comprehensive health check completed",
            user_id=str(current_user.id),
            overall_status=health_report["overall_status"],
            total_checks=health_report["summary"]["total_checks"],
            unhealthy_checks=health_report["summary"]["unhealthy_checks"]
        )
        
        return health_report
        
    except Exception as e:
        logger.error(
            "Comprehensive health check failed",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/simple")
async def simple_health_check() -> Dict[str, Any]:
    """Simple health check endpoint for load balancers."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ats-backend"
    }


@router.get("/metrics")
async def get_system_metrics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive system metrics."""
    try:
        with performance_logger.log_operation_time(
            "get_system_metrics",
            user_id=str(current_user.id)
        ):
            metrics = metrics_collector.get_comprehensive_metrics()
        
        logger.info(
            "System metrics retrieved",
            user_id=str(current_user.id),
            metric_types=len(metrics.get("metric_counts", {})),
            processing_metrics=metrics.get("total_processing_metrics", 0)
        )
        
        return metrics
        
    except Exception as e:
        logger.error(
            "Failed to get system metrics",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system metrics: {str(e)}"
        )


@router.get("/metrics/processing")
async def get_processing_metrics(
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    hours_back: int = Query(24, description="Hours to look back"),
    limit: int = Query(100, description="Maximum number of results"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get processing metrics with filtering."""
    try:
        since = datetime.utcnow() - timedelta(hours=hours_back)
        target_client_id = client_id or str(current_user.client_id)
        
        processing_metrics = metrics_collector.get_processing_metrics_history(
            operation=operation,
            client_id=target_client_id,
            since=since,
            limit=limit
        )
        
        logger.info(
            "Processing metrics retrieved",
            user_id=str(current_user.id),
            operation=operation,
            client_id=target_client_id,
            hours_back=hours_back,
            results_count=len(processing_metrics)
        )
        
        return {
            "metrics": [m.to_dict() for m in processing_metrics],
            "filters": {
                "operation": operation,
                "client_id": target_client_id,
                "hours_back": hours_back,
                "limit": limit
            },
            "total_results": len(processing_metrics),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to get processing metrics",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get processing metrics: {str(e)}"
        )


@router.get("/metrics/summary/{metric_name}")
async def get_metric_summary(
    metric_name: str,
    hours_back: int = Query(24, description="Hours to look back"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get summary statistics for a specific metric."""
    try:
        since = datetime.utcnow() - timedelta(hours=hours_back)
        summary = metrics_collector.get_metric_summary(metric_name, since=since)
        
        logger.info(
            "Metric summary retrieved",
            user_id=str(current_user.id),
            metric_name=metric_name,
            hours_back=hours_back,
            data_points=summary.get("count", 0)
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            "Failed to get metric summary",
            user_id=str(current_user.id),
            metric_name=metric_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metric summary: {str(e)}"
        )


@router.post("/metrics/cleanup")
async def cleanup_old_metrics(
    hours_old: int = Query(24, description="Remove metrics older than this many hours"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clean up old metrics to free memory."""
    try:
        older_than = timedelta(hours=hours_old)
        metrics_collector.cleanup_old_metrics(older_than)
        
        logger.info(
            "Metrics cleanup completed",
            user_id=str(current_user.id),
            hours_old=hours_old
        )
        
        return {
            "success": True,
            "message": f"Cleaned up metrics older than {hours_old} hours",
            "hours_old": hours_old,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to cleanup metrics",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup metrics: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed status of a specific task."""
    try:
        with performance_logger.log_operation_time(
            "get_task_status",
            user_id=str(current_user.id),
            task_id=task_id
        ):
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
        with performance_logger.log_operation_time(
            "get_active_tasks",
            user_id=str(current_user.id)
        ):
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
        with performance_logger.log_operation_time(
            "get_worker_stats",
            user_id=str(current_user.id)
        ):
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
        with performance_logger.log_operation_time(
            "get_queue_info",
            user_id=str(current_user.id)
        ):
            queue_info = task_monitor.get_queue_lengths()
        
        # Record queue metrics
        metrics_collector.record_metric(
            "api.queue_info_requests",
            1,
            {"user_id": str(current_user.id)}
        )
        
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


@router.post("/monitoring/performance")
async def trigger_performance_monitoring(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Trigger system performance monitoring task."""
    try:
        from ats_backend.workers.email_tasks import monitor_system_performance
        
        # Queue the performance monitoring task
        task = monitor_system_performance.delay()
        
        # Wait for result (since performance monitoring should be quick)
        result = task.get(timeout=30)
        
        logger.info(
            "Performance monitoring completed",
            user_id=str(current_user.id),
            task_id=task.id,
            alerts_count=len(result.get("alerts", []))
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Failed to trigger performance monitoring",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger performance monitoring: {str(e)}"
        )


@router.get("/monitoring/health-check")
async def trigger_health_check(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Trigger worker health check task."""
    try:
        from ats_backend.workers.email_tasks import health_check_workers
        
        # Queue the health check task
        task = health_check_workers.delay()
        
        # Wait for result (since health check should be quick)
        result = task.get(timeout=30)
        
        logger.info(
            "Health check completed",
            user_id=str(current_user.id),
            task_id=task.id,
            healthy=result.get("healthy", False)
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Failed to trigger health check",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger health check: {str(e)}"
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