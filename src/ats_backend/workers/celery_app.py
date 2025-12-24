"""Celery application configuration with comprehensive error handling."""

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_retry, worker_ready, worker_shutdown
import structlog
from datetime import datetime
from typing import Dict, Any
import sys
import traceback

from ats_backend.core.config import settings
from ats_backend.core.error_handling import (
    ErrorHandler, error_handler, RetryConfig, RetryManager,
    ErrorContext, ErrorCategory, ErrorSeverity, ATSError
)
from ats_backend.core.logging import performance_logger, system_logger

logger = structlog.get_logger(__name__)

# Create Celery app with enhanced error handling
celery_app = Celery(
    "ats_backend",
    broker=settings.celery_broker_url_computed,
    backend=settings.celery_result_backend_computed,
    include=[
        "ats_backend.workers.resume_tasks",
        "ats_backend.workers.email_tasks"
    ]
)

# Configure Celery with comprehensive error handling
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
    
    # Enhanced task time limits for complex operations
    task_soft_time_limit=600,   # 10 minutes
    task_time_limit=900,        # 15 minutes
    
    # Result backend settings
    result_expires=7200,        # 2 hours
    result_persistent=True,
    
    # Enhanced retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,    # 1 minute default retry delay
    task_max_retries=3,             # Default max retries
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task compression
    task_compression="gzip",
    result_compression="gzip",
    
    # Worker pool settings with error recovery
    worker_pool="prefork",
    worker_pool_restarts=True,
    worker_disable_rate_limits=False,
    
    # Enhanced beat schedule for monitoring and cleanup
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
        'monitor-queue-health': {
            'task': 'monitor_queue_health',
            'schedule': 180.0,  # Every 3 minutes
        },
        'cleanup-stale-tasks': {
            'task': 'cleanup_stale_tasks',
            'schedule': 1800.0,  # Every 30 minutes
        },
    },
)

# Task autodiscovery
celery_app.autodiscover_tasks([
    "ats_backend.workers"
])


# Enhanced task monitoring and logging signals
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task start with comprehensive context."""
    context = {
        "task_id": task_id,
        "task_name": task.name if task else sender,
        "args_count": len(args) if args else 0,
        "kwargs_keys": list(kwargs.keys()) if kwargs else [],
        "timestamp": datetime.utcnow().isoformat(),
        "worker_hostname": kwds.get('hostname', 'unknown')
    }
    
    # Extract client_id from kwargs if available
    if kwargs and 'client_id' in kwargs:
        context['client_id'] = str(kwargs['client_id'])
    
    logger.info("Task started", **context)
    
    # Log performance metrics
    performance_logger.log_operation_time(
        f"celery_task_{task.name if task else sender}",
        task_id=task_id
    ).__enter__()


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Log task completion with comprehensive metrics."""
    context = {
        "task_id": task_id,
        "task_name": task.name if task else sender,
        "state": state,
        "success": state == "SUCCESS",
        "timestamp": datetime.utcnow().isoformat(),
        "worker_hostname": kwds.get('hostname', 'unknown')
    }
    
    # Extract client_id from kwargs if available
    if kwargs and 'client_id' in kwargs:
        context['client_id'] = str(kwargs['client_id'])
    
    # Add result information for successful tasks
    if state == "SUCCESS" and retval:
        if isinstance(retval, dict):
            context['result_keys'] = list(retval.keys())
            if 'processed_items' in retval:
                context['processed_items'] = retval['processed_items']
    
    logger.info("Task completed", **context)


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failure with comprehensive error context."""
    error_context = ErrorContext(
        operation=f"celery_task_{sender.name if sender else 'unknown'}",
        component="celery_worker",
        additional_data={
            "task_id": task_id,
            "worker_hostname": kwds.get('hostname', 'unknown')
        }
    )
    
    # Handle the error through our error handling system
    try:
        ats_error = error_handler.handle_error(exception, error_context)
        
        logger.error(
            "Task failed with handled error",
            task_id=task_id,
            task_name=sender.name if sender else "unknown",
            error_category=ats_error.category.value,
            error_severity=ats_error.severity.value,
            exception=str(exception),
            exception_type=type(exception).__name__,
            timestamp=datetime.utcnow().isoformat(),
            worker_hostname=kwds.get('hostname', 'unknown')
        )
        
    except Exception as handling_error:
        # Fallback logging if error handling fails
        logger.critical(
            "Task failed and error handling failed",
            task_id=task_id,
            task_name=sender.name if sender else "unknown",
            original_exception=str(exception),
            handling_error=str(handling_error),
            timestamp=datetime.utcnow().isoformat()
        )


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Log task retry with enhanced context."""
    retry_context = {
        "task_id": task_id,
        "task_name": sender.name if sender else "unknown",
        "reason": str(reason),
        "retry_count": getattr(sender.request, 'retries', 0) if sender else 0,
        "max_retries": getattr(sender, 'max_retries', 3) if sender else 3,
        "timestamp": datetime.utcnow().isoformat(),
        "worker_hostname": kwds.get('hostname', 'unknown')
    }
    
    logger.warning("Task retry", **retry_context)


@worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Log worker ready with system information."""
    worker_info = {
        "worker_hostname": sender.hostname if sender else "unknown",
        "timestamp": datetime.utcnow().isoformat(),
        "python_version": sys.version,
        "celery_version": celery_app.version
    }
    
    system_logger.log_system_startup(
        "celery_worker",
        **worker_info
    )
    
    logger.info("Celery worker ready", **worker_info)


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwds):
    """Log worker shutdown."""
    worker_info = {
        "worker_hostname": sender.hostname if sender else "unknown",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    system_logger.log_system_shutdown(
        "celery_worker",
        **worker_info
    )
    
    logger.info("Celery worker shutting down", **worker_info)


# Enhanced task monitoring utilities
class TaskMonitor:
    """Utilities for monitoring Celery tasks with comprehensive error handling."""
    
    def __init__(self):
        self.logger = structlog.get_logger("task_monitor")
        self.error_handler = ErrorHandler()
    
    def get_task_info(self, task_id: str) -> Dict[str, Any]:
        """Get comprehensive task information with error handling."""
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
                    
                    # Classify the error
                    if task_result.info:
                        error_context = ErrorContext(
                            operation="get_task_info",
                            component="task_monitor",
                            additional_data={"task_id": task_id}
                        )
                        
                        try:
                            ats_error = self.error_handler.handle_error(
                                Exception(str(task_result.info)), 
                                error_context
                            )
                            info["error_category"] = ats_error.category.value
                            info["error_severity"] = ats_error.severity.value
                        except Exception:
                            pass  # Don't fail if error classification fails
            else:
                info["info"] = task_result.info
            
            return info
            
        except Exception as e:
            self.logger.error("Failed to get task info", task_id=task_id, error=str(e))
            return {
                "task_id": task_id,
                "error": f"Failed to get task info: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_active_tasks(self) -> Dict[str, Any]:
        """Get information about active tasks with error handling."""
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                return {"active_tasks": {}, "total_active": 0}
            
            total_active = sum(len(tasks) for tasks in active_tasks.values())
            
            # Add task health analysis
            task_health = self._analyze_task_health(active_tasks)
            
            return {
                "active_tasks": active_tasks,
                "total_active": total_active,
                "workers": list(active_tasks.keys()),
                "task_health": task_health,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get active tasks", error=str(e))
            return {
                "error": f"Failed to get active tasks: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics with health analysis."""
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                return {"workers": {}, "total_workers": 0}
            
            # Analyze worker health
            worker_health = self._analyze_worker_health(stats)
            
            return {
                "workers": stats,
                "total_workers": len(stats),
                "worker_health": worker_health,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get worker stats", error=str(e))
            return {
                "error": f"Failed to get worker stats: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_queue_lengths(self) -> Dict[str, Any]:
        """Get queue lengths with health analysis."""
        try:
            from ats_backend.core.redis import get_redis_client
            import asyncio
            
            # Handle async Redis client
            async def _get_queue_info():
                redis_client = await get_redis_client()
                try:
                    queues = ["resume_processing", "email_processing", "celery"]
                    queue_info = {}
                    
                    for queue in queues:
                        length = await redis_client.llen(queue)
                        queue_info[queue] = length
                    
                    return queue_info
                finally:
                    await redis_client.close()
            
            # Run async function
            try:
                loop = asyncio.get_event_loop()
                queue_info = loop.run_until_complete(_get_queue_info())
            except RuntimeError:
                # No event loop running, create one
                queue_info = asyncio.run(_get_queue_info())
            
            # Analyze queue health
            queue_health = self._analyze_queue_health(queue_info)
            
            return {
                "queues": queue_info,
                "total_queued": sum(queue_info.values()),
                "queue_health": queue_health,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get queue lengths", error=str(e))
            return {
                "error": f"Failed to get queue lengths: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _analyze_task_health(self, active_tasks: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze health of active tasks."""
        health = {
            "status": "healthy",
            "issues": [],
            "recommendations": []
        }
        
        try:
            total_tasks = sum(len(tasks) for tasks in active_tasks.values())
            
            # Check for too many active tasks
            if total_tasks > 50:
                health["status"] = "warning"
                health["issues"].append(f"High number of active tasks: {total_tasks}")
                health["recommendations"].append("Consider scaling workers or optimizing task performance")
            
            # Check for stuck tasks (would need task start times)
            # This is a placeholder for more sophisticated analysis
            
        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Failed to analyze task health: {str(e)}")
        
        return health
    
    def _analyze_worker_health(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze health of workers."""
        health = {
            "status": "healthy",
            "issues": [],
            "recommendations": []
        }
        
        try:
            if not stats:
                health["status"] = "critical"
                health["issues"].append("No workers available")
                health["recommendations"].append("Start Celery workers")
                return health
            
            # Analyze worker statistics
            for worker_name, worker_stats in stats.items():
                if 'pool' in worker_stats:
                    pool_stats = worker_stats['pool']
                    
                    # Check worker pool health
                    if 'max-concurrency' in pool_stats and 'processes' in pool_stats:
                        max_concurrency = pool_stats['max-concurrency']
                        active_processes = len(pool_stats.get('processes', []))
                        
                        if active_processes < max_concurrency * 0.5:
                            health["status"] = "warning"
                            health["issues"].append(f"Worker {worker_name} has low process utilization")
            
        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Failed to analyze worker health: {str(e)}")
        
        return health
    
    def _analyze_queue_health(self, queue_info: Dict[str, int]) -> Dict[str, Any]:
        """Analyze health of queues."""
        health = {
            "status": "healthy",
            "issues": [],
            "recommendations": []
        }
        
        try:
            for queue_name, length in queue_info.items():
                if length > 100:
                    health["status"] = "warning"
                    health["issues"].append(f"Queue {queue_name} has high backlog: {length}")
                    health["recommendations"].append(f"Consider scaling workers for {queue_name} queue")
                elif length > 500:
                    health["status"] = "critical"
                    health["issues"].append(f"Queue {queue_name} has critical backlog: {length}")
                    health["recommendations"].append(f"Urgent: Scale workers for {queue_name} queue")
            
        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Failed to analyze queue health: {str(e)}")
        
        return health
    
    def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive health status of the entire Celery system."""
        try:
            active_tasks = self.get_active_tasks()
            worker_stats = self.get_worker_stats()
            queue_lengths = self.get_queue_lengths()
            
            # Determine overall health
            health_statuses = []
            if 'task_health' in active_tasks:
                health_statuses.append(active_tasks['task_health']['status'])
            if 'worker_health' in worker_stats:
                health_statuses.append(worker_stats['worker_health']['status'])
            if 'queue_health' in queue_lengths:
                health_statuses.append(queue_lengths['queue_health']['status'])
            
            # Determine overall status
            if 'critical' in health_statuses:
                overall_status = 'critical'
            elif 'error' in health_statuses:
                overall_status = 'error'
            elif 'warning' in health_statuses:
                overall_status = 'warning'
            else:
                overall_status = 'healthy'
            
            return {
                "overall_status": overall_status,
                "active_tasks": active_tasks,
                "worker_stats": worker_stats,
                "queue_lengths": queue_lengths,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get comprehensive health", error=str(e))
            return {
                "overall_status": "error",
                "error": f"Failed to get comprehensive health: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }


# Global task monitor instance
task_monitor = TaskMonitor()


# Enhanced task base class with error handling
class BaseTask(celery_app.Task):
    """Base task class with comprehensive error handling and retry logic."""
    
    def __init__(self):
        self.logger = structlog.get_logger(self.__class__.__name__)
        self.retry_manager = RetryManager()
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure with comprehensive error logging."""
        error_context = ErrorContext(
            operation=self.name,
            component="celery_task",
            additional_data={
                "task_id": task_id,
                "args": args[:3] if args else [],  # Limit args for logging
                "kwargs_keys": list(kwargs.keys()) if kwargs else []
            }
        )
        
        # Extract client_id if available
        if kwargs and 'client_id' in kwargs:
            error_context.client_id = str(kwargs['client_id'])
        
        try:
            ats_error = error_handler.handle_error(exc, error_context)
            
            self.logger.error(
                "Task failed with comprehensive error handling",
                task_id=task_id,
                task_name=self.name,
                error_category=ats_error.category.value,
                error_severity=ats_error.severity.value,
                client_id=error_context.client_id
            )
            
        except Exception as handling_error:
            self.logger.critical(
                "Task failure and error handling both failed",
                task_id=task_id,
                task_name=self.name,
                original_error=str(exc),
                handling_error=str(handling_error)
            )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry with enhanced logging."""
        self.logger.warning(
            "Task retry with enhanced context",
            task_id=task_id,
            task_name=self.name,
            retry_count=self.request.retries,
            max_retries=self.max_retries,
            exception=str(exc),
            client_id=str(kwargs.get('client_id')) if kwargs and 'client_id' in kwargs else None
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success with metrics logging."""
        self.logger.info(
            "Task completed successfully",
            task_id=task_id,
            task_name=self.name,
            result_type=type(retval).__name__,
            client_id=str(kwargs.get('client_id')) if kwargs and 'client_id' in kwargs else None
        )


# Set the base task class
celery_app.Task = BaseTask


logger.info(
    "Celery app configured with comprehensive error handling",
    broker=settings.celery_broker_url_computed,
    backend=settings.celery_result_backend_computed,
    queues=["resume_processing", "email_processing"],
    error_handling_enabled=True,
    monitoring_enabled=True
)