"""Celery application configuration."""

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_retry, worker_ready
import structlog
from datetime import datetime
from typing import Dict, Any

from ats_backend.core.config import settings

logger = structlog.get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "ats_backend",
    broker=settings.celery_broker_url_computed,
    backend=settings.celery_result_backend_computed,
    include=[
        "ats_backend.workers.resume_tasks",
        "ats_backend.workers.email_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    # Task routing
    task_routes={
        "ats_backend.workers.resume_tasks.*": {"queue": "resume_processing"},
        "ats_backend.workers.email_tasks.*": {"queue": "email_processing"},
    },
    
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Task execution
    task_always_eager=False,
    task_eager_propagates=True,
    task_ignore_result=False,
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Task time limits (increased for resume processing)
    task_soft_time_limit=600,   # 10 minutes
    task_time_limit=900,        # 15 minutes
    
    # Result backend settings
    result_expires=7200,        # 2 hours (increased for better debugging)
    result_persistent=True,
    
    # Retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task compression
    task_compression="gzip",
    result_compression="gzip",
    
    # Worker pool settings
    worker_pool="prefork",
    worker_pool_restarts=True,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'cleanup-old-files': {
            'task': 'cleanup_old_files',
            'schedule': 86400.0,  # Daily
            'kwargs': {'days_old': 30}
        },
        'cleanup-failed-jobs': {
            'task': 'cleanup_failed_jobs_all_clients',
            'schedule': 3600.0,  # Hourly
            'kwargs': {'max_age_hours': 24}
        },
        'health-check-workers': {
            'task': 'health_check_workers',
            'schedule': 300.0,  # Every 5 minutes
        },
    },
)

# Task autodiscovery
celery_app.autodiscover_tasks([
    "ats_backend.workers"
])


# Task monitoring and logging signals
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task start."""
    logger.info(
        "Task started",
        task_id=task_id,
        task_name=task.name if task else sender,
        args_count=len(args) if args else 0,
        kwargs_keys=list(kwargs.keys()) if kwargs else [],
        timestamp=datetime.utcnow().isoformat()
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Log task completion."""
    logger.info(
        "Task completed",
        task_id=task_id,
        task_name=task.name if task else sender,
        state=state,
        success=state == "SUCCESS",
        timestamp=datetime.utcnow().isoformat()
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failure."""
    logger.error(
        "Task failed",
        task_id=task_id,
        task_name=sender.name if sender else "unknown",
        exception=str(exception),
        exception_type=type(exception).__name__,
        timestamp=datetime.utcnow().isoformat()
    )


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Log task retry."""
    logger.warning(
        "Task retry",
        task_id=task_id,
        task_name=sender.name if sender else "unknown",
        reason=str(reason),
        timestamp=datetime.utcnow().isoformat()
    )


@worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Log worker ready."""
    logger.info(
        "Celery worker ready",
        worker_hostname=sender.hostname if sender else "unknown",
        timestamp=datetime.utcnow().isoformat()
    )


# Task monitoring utilities
class TaskMonitor:
    """Utilities for monitoring Celery tasks."""
    
    @staticmethod
    def get_task_info(task_id: str) -> Dict[str, Any]:
        """Get comprehensive task information."""
        try:
            task_result = celery_app.AsyncResult(task_id)
            
            info = {
                "task_id": task_id,
                "state": task_result.state,
                "ready": task_result.ready(),
                "successful": task_result.successful() if task_result.ready() else None,
                "failed": task_result.failed() if task_result.ready() else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if task_result.ready():
                if task_result.successful():
                    info["result"] = task_result.result
                elif task_result.failed():
                    info["error"] = str(task_result.info)
                    info["traceback"] = task_result.traceback
            else:
                info["info"] = task_result.info
            
            return info
            
        except Exception as e:
            return {
                "task_id": task_id,
                "error": f"Failed to get task info: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def get_active_tasks() -> Dict[str, Any]:
        """Get information about active tasks."""
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                return {"active_tasks": {}, "total_active": 0}
            
            total_active = sum(len(tasks) for tasks in active_tasks.values())
            
            return {
                "active_tasks": active_tasks,
                "total_active": total_active,
                "workers": list(active_tasks.keys()),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "error": f"Failed to get active tasks: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def get_worker_stats() -> Dict[str, Any]:
        """Get worker statistics."""
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                return {"workers": {}, "total_workers": 0}
            
            return {
                "workers": stats,
                "total_workers": len(stats),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "error": f"Failed to get worker stats: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def get_queue_lengths() -> Dict[str, Any]:
        """Get queue lengths."""
        try:
            from ats_backend.core.redis import get_redis_client
            
            redis_client = get_redis_client()
            
            queues = ["resume_processing", "email_processing", "celery"]  # Default queue
            queue_info = {}
            
            for queue in queues:
                length = redis_client.llen(queue)
                queue_info[queue] = length
            
            return {
                "queues": queue_info,
                "total_queued": sum(queue_info.values()),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "error": f"Failed to get queue lengths: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }


# Global task monitor instance
task_monitor = TaskMonitor()

logger.info(
    "Celery app configured",
    broker=settings.celery_broker_url_computed,
    backend=settings.celery_result_backend_computed,
    queues=["resume_processing", "email_processing"]
)