"""Celery tasks for email processing."""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from celery import Task
import structlog

from ats_backend.workers.celery_app import celery_app
from ats_backend.core.database import get_db
from ats_backend.core.metrics import metrics_collector
from ats_backend.core.logging import performance_logger, error_logger
from ats_backend.email.processor import EmailProcessor
from ats_backend.email.models import EmailMessage, EmailIngestionResponse

logger = structlog.get_logger(__name__)


class EmailProcessingTask(Task):
    """Base task class for email processing with enhanced error handling."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    retry_backoff_max = 300  # Maximum backoff of 5 minutes
    retry_jitter = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure with detailed logging."""
        error_logger.log_error_with_context(
            error=exc,
            operation="email_processing_task",
            request_data={
                "task_id": task_id,
                "args": args,
                "kwargs": kwargs
            }
        )
        
        # Record failure metrics
        metrics_collector.record_metric(
            "email.processing.failures",
            1,
            {
                "task_name": self.name,
                "error_type": type(exc).__name__,
                "client_id": kwargs.get("client_id", "unknown")
            }
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry with detailed logging."""
        logger.warning(
            "Email processing task retrying",
            task_id=task_id,
            exception=str(exc),
            exception_type=type(exc).__name__,
            retry_count=self.request.retries,
            max_retries=self.max_retries,
            countdown=self.retry_kwargs.get("countdown", 60)
        )
        
        # Record retry metrics
        metrics_collector.record_metric(
            "email.processing.retries",
            1,
            {
                "task_name": self.name,
                "error_type": type(exc).__name__,
                "retry_count": self.request.retries,
                "client_id": kwargs.get("client_id", "unknown")
            }
        )


@celery_app.task(bind=True, base=EmailProcessingTask, name="process_email_message")
def process_email_message(
    self,
    client_id: str,
    email_data: Dict[str, Any],
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """Process an email message asynchronously.
    
    Args:
        client_id: Client UUID string
        email_data: Email message data dictionary
        user_id: User UUID string (optional)
        ip_address: IP address of the request (optional)
        user_agent: User agent of the request (optional)
        
    Returns:
        Dictionary with processing results
    """
    # Start processing metrics
    processing_metrics = metrics_collector.start_processing_metrics(
        operation="email_processing",
        client_id=client_id,
        user_id=user_id
    )
    
    try:
        with performance_logger.log_operation_time(
            "process_email_message",
            task_id=self.request.id,
            client_id=client_id,
            message_id=email_data.get("message_id")
        ):
            logger.info(
                "Starting email processing task",
                task_id=self.request.id,
                client_id=client_id,
                message_id=email_data.get("message_id")
            )
            
            # Parse email data
            email = EmailMessage(**email_data)
            processing_metrics.items_processed = len(email.attachments)
            
            # Get database session
            db = next(get_db())
            
            try:
                # Process email
                processor = EmailProcessor()
                result = processor.process_email(
                    db=db,
                    client_id=UUID(client_id),
                    email=email,
                    user_id=UUID(user_id) if user_id else None,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Update processing metrics
                processing_metrics.success_count = result.processed_attachments
                processing_metrics.error_count = len(email.attachments) - result.processed_attachments
                
                # Record success metrics
                metrics_collector.record_metric(
                    "email.processing.success",
                    1,
                    {"client_id": client_id, "attachments": len(email.attachments)}
                )
                
                logger.info(
                    "Email processing task completed",
                    task_id=self.request.id,
                    client_id=client_id,
                    message_id=email.message_id,
                    success=result.success,
                    jobs_created=len(result.job_ids),
                    attachments_processed=result.processed_attachments
                )
                
                return {
                    "success": result.success,
                    "message": result.message,
                    "job_ids": [str(job_id) for job_id in result.job_ids],
                    "processed_attachments": result.processed_attachments,
                    "duplicate_message_id": result.duplicate_message_id,
                    "task_id": self.request.id
                }
                
            finally:
                db.close()
                
    except Exception as e:
        processing_metrics.error_count += 1
        
        error_logger.log_error_with_context(
            error=e,
            operation="process_email_message",
            client_id=client_id,
            user_id=user_id,
            request_data={
                "task_id": self.request.id,
                "message_id": email_data.get("message_id"),
                "retry_count": self.request.retries
            }
        )
        
        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e)
    
    finally:
        # Finish processing metrics
        metrics_collector.finish_processing_metrics(processing_metrics)


@celery_app.task(bind=True, name="cleanup_old_files")
def cleanup_old_files(self, days_old: int = 30) -> Dict[str, Any]:
    """Clean up old files from storage.
    
    Args:
        days_old: Number of days after which files should be cleaned up
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(
            "Starting file cleanup task",
            task_id=self.request.id,
            days_old=days_old
        )
        
        from ats_backend.email.storage import FileStorageService
        
        storage_service = FileStorageService()
        files_cleaned = storage_service.cleanup_old_files(days_old)
        
        logger.info(
            "File cleanup task completed",
            task_id=self.request.id,
            files_cleaned=files_cleaned,
            days_old=days_old
        )
        
        return {
            "success": True,
            "files_cleaned": files_cleaned,
            "days_old": days_old,
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(
            "File cleanup task failed",
            task_id=self.request.id,
            days_old=days_old,
            error=str(e)
        )
        
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="cleanup_failed_jobs")
def cleanup_failed_jobs(
    self,
    client_id: str,
    max_age_hours: int = 24
) -> Dict[str, Any]:
    """Clean up old failed jobs for a client.
    
    Args:
        client_id: Client UUID string
        max_age_hours: Maximum age in hours for failed jobs to keep
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(
            "Starting failed jobs cleanup task",
            task_id=self.request.id,
            client_id=client_id,
            max_age_hours=max_age_hours
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            processor = EmailProcessor()
            jobs_cleaned = processor.cleanup_failed_jobs(
                db, UUID(client_id), max_age_hours
            )
            
            logger.info(
                "Failed jobs cleanup task completed",
                task_id=self.request.id,
                client_id=client_id,
                jobs_cleaned=jobs_cleaned
            )
            
            return {
                "success": True,
                "jobs_cleaned": jobs_cleaned,
                "client_id": client_id,
                "max_age_hours": max_age_hours,
                "task_id": self.request.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Failed jobs cleanup task failed",
            task_id=self.request.id,
            client_id=client_id,
            error=str(e)
        )
        
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="validate_email_format")
def validate_email_format(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate email message format asynchronously.
    
    Args:
        email_data: Email message data dictionary
        
    Returns:
        Dictionary with validation results
    """
    try:
        logger.info(
            "Starting email validation task",
            task_id=self.request.id,
            message_id=email_data.get("message_id")
        )
        
        # Parse and validate email
        email = EmailMessage(**email_data)
        
        processor = EmailProcessor()
        validation_errors = processor.validate_email_message(email)
        
        is_valid = len(validation_errors) == 0
        
        logger.info(
            "Email validation task completed",
            task_id=self.request.id,
            message_id=email.message_id,
            is_valid=is_valid,
            error_count=len(validation_errors)
        )
        
        return {
            "valid": is_valid,
            "errors": validation_errors,
            "message_id": email.message_id,
            "attachment_count": len(email.attachments),
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(
            "Email validation task failed",
            task_id=self.request.id,
            message_id=email_data.get("message_id"),
            error=str(e)
        )
        
        return {
            "valid": False,
            "errors": [f"Validation failed: {str(e)}"],
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="get_processing_stats")
def get_processing_stats(
    self,
    client_id: str,
    days_back: int = 30
) -> Dict[str, Any]:
    """Get processing statistics for a client asynchronously.
    
    Args:
        client_id: Client UUID string
        days_back: Number of days to look back for statistics
        
    Returns:
        Dictionary with processing statistics
    """
    try:
        logger.info(
            "Starting processing stats task",
            task_id=self.request.id,
            client_id=client_id,
            days_back=days_back
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            processor = EmailProcessor()
            stats = processor.get_processing_statistics(
                db, UUID(client_id), days_back
            )
            
            logger.info(
                "Processing stats task completed",
                task_id=self.request.id,
                client_id=client_id
            )
            
            stats["task_id"] = self.request.id
            return stats
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Processing stats task failed",
            task_id=self.request.id,
            client_id=client_id,
            error=str(e)
        )
        
        return {
            "error": str(e),
            "client_id": client_id,
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="cleanup_failed_jobs_all_clients")
def cleanup_failed_jobs_all_clients(
    self,
    max_age_hours: int = 24
) -> Dict[str, Any]:
    """Clean up old failed jobs for all clients (periodic task).
    
    Args:
        max_age_hours: Maximum age in hours for failed jobs to keep
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(
            "Starting global failed jobs cleanup task",
            task_id=self.request.id,
            max_age_hours=max_age_hours
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            from ats_backend.services.client_service import ClientService
            
            client_service = ClientService()
            processor = EmailProcessor()
            
            # Get all clients
            clients = client_service.get_all_clients(db)
            
            total_jobs_cleaned = 0
            clients_processed = 0
            
            for client in clients:
                try:
                    jobs_cleaned = processor.cleanup_failed_jobs(
                        db, client.id, max_age_hours
                    )
                    total_jobs_cleaned += jobs_cleaned
                    clients_processed += 1
                    
                    logger.debug(
                        "Cleaned failed jobs for client",
                        client_id=str(client.id),
                        jobs_cleaned=jobs_cleaned
                    )
                    
                except Exception as e:
                    logger.error(
                        "Failed to clean jobs for client",
                        client_id=str(client.id),
                        error=str(e)
                    )
            
            logger.info(
                "Global failed jobs cleanup task completed",
                task_id=self.request.id,
                clients_processed=clients_processed,
                total_jobs_cleaned=total_jobs_cleaned
            )
            
            return {
                "success": True,
                "clients_processed": clients_processed,
                "total_jobs_cleaned": total_jobs_cleaned,
                "max_age_hours": max_age_hours,
                "task_id": self.request.id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Global failed jobs cleanup task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="health_check_workers")
def health_check_workers(self) -> Dict[str, Any]:
    """Periodic health check task for workers.
    
    Returns:
        Dictionary with health check results
    """
    try:
        logger.info(
            "Starting worker health check task",
            task_id=self.request.id
        )
        
        from ats_backend.workers.celery_app import task_monitor
        
        # Get worker statistics
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        # Determine health status
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
        
        # Check for stuck tasks (active for too long)
        active_task_data = active_tasks.get("active_tasks", {})
        for worker_name, tasks in active_task_data.items():
            if len(tasks) > 10:  # Too many active tasks per worker
                issues.append(f"Worker {worker_name} has {len(tasks)} active tasks")
        
        health_result = {
            "healthy": healthy,
            "status": "healthy" if healthy else "degraded",
            "issues": issues,
            "summary": {
                "workers": worker_stats.get("total_workers", 0),
                "active_tasks": active_tasks.get("total_active", 0),
                "queued_tasks": total_queued
            },
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.request.id
        }
        
        if not healthy:
            logger.warning(
                "Worker health check detected issues",
                task_id=self.request.id,
                issues=issues
            )
        else:
            logger.info(
                "Worker health check passed",
                task_id=self.request.id
            )
        
        return health_result
        
    except Exception as e:
        logger.error(
            "Worker health check task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "healthy": False,
            "status": "error",
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="monitor_system_performance")
def monitor_system_performance(self) -> Dict[str, Any]:
    """Monitor system performance metrics.
    
    Returns:
        Dictionary with performance metrics
    """
    try:
        logger.info(
            "Starting system performance monitoring task",
            task_id=self.request.id
        )
        
        import psutil
        from datetime import datetime, timedelta
        from ats_backend.workers.celery_app import task_monitor
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get Celery metrics
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        # Calculate performance indicators
        performance_metrics = {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free_gb": disk.free / (1024**3)
            },
            "celery": {
                "total_workers": worker_stats.get("total_workers", 0),
                "active_tasks": active_tasks.get("total_active", 0),
                "queued_tasks": queue_info.get("total_queued", 0),
                "queue_breakdown": queue_info.get("queues", {})
            },
            "alerts": [],
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.request.id
        }
        
        # Generate alerts based on thresholds
        if cpu_percent > 80:
            performance_metrics["alerts"].append(f"High CPU usage: {cpu_percent}%")
        
        if memory.percent > 85:
            performance_metrics["alerts"].append(f"High memory usage: {memory.percent}%")
        
        if (disk.used / disk.total) * 100 > 90:
            performance_metrics["alerts"].append(f"High disk usage: {(disk.used / disk.total) * 100:.1f}%")
        
        if queue_info.get("total_queued", 0) > 50:
            performance_metrics["alerts"].append(f"High queue backlog: {queue_info.get('total_queued', 0)} tasks")
        
        if worker_stats.get("total_workers", 0) == 0:
            performance_metrics["alerts"].append("No workers available")
        
        # Record performance metrics
        metrics_collector.record_metric("system.cpu_percent", cpu_percent)
        metrics_collector.record_metric("system.memory_percent", memory.percent)
        metrics_collector.record_metric("system.disk_percent", (disk.used / disk.total) * 100)
        
        # Log alerts if any
        if performance_metrics["alerts"]:
            logger.warning(
                "System performance alerts detected",
                task_id=self.request.id,
                alerts=performance_metrics["alerts"]
            )
        else:
            logger.info(
                "System performance monitoring completed - no alerts",
                task_id=self.request.id
            )
        
        return performance_metrics
        
    except Exception as e:
        logger.error(
            "System performance monitoring task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="health_check_workers")
def health_check_workers(self) -> Dict[str, Any]:
    """Periodic health check task for workers.
    
    Returns:
        Dictionary with health check results
    """
    try:
        logger.info(
            "Starting worker health check task",
            task_id=self.request.id
        )
        
        from ats_backend.workers.celery_app import task_monitor
        
        # Get worker statistics
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        # Determine health status
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
        
        # Check for stuck tasks (active for too long)
        active_task_data = active_tasks.get("active_tasks", {})
        for worker_name, tasks in active_task_data.items():
            for task in tasks:
                # This is a simplified check - in production you'd want to track task start times
                if len(tasks) > 10:  # Too many active tasks per worker
                    issues.append(f"Worker {worker_name} has {len(tasks)} active tasks")
        
        health_result = {
            "healthy": healthy,
            "status": "healthy" if healthy else "degraded",
            "issues": issues,
            "summary": {
                "workers": worker_stats.get("total_workers", 0),
                "active_tasks": active_tasks.get("total_active", 0),
                "queued_tasks": total_queued
            },
            "timestamp": logger.info.__self__.timestamp if hasattr(logger.info.__self__, 'timestamp') else None,
            "task_id": self.request.id
        }
        
        if not healthy:
            logger.warning(
                "Worker health check detected issues",
                task_id=self.request.id,
                issues=issues
            )
        else:
            logger.info(
                "Worker health check passed",
                task_id=self.request.id
            )
        
        return health_result
        
    except Exception as e:
        logger.error(
            "Worker health check task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "healthy": False,
            "status": "error",
            "error": str(e),
            "task_id": self.request.id
        }
    """Get processing statistics for a client asynchronously.
    
    Args:
        client_id: Client UUID string
        days_back: Number of days to look back for statistics
        
    Returns:
        Dictionary with processing statistics
    """
    try:
        logger.info(
            "Starting processing stats task",
            task_id=self.request.id,
            client_id=client_id,
            days_back=days_back
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            processor = EmailProcessor()
            stats = processor.get_processing_statistics(
                db, UUID(client_id), days_back
            )
            
            logger.info(
                "Processing stats task completed",
                task_id=self.request.id,
                client_id=client_id
            )
            
            stats["task_id"] = self.request.id
            return stats
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            "Processing stats task failed",
            task_id=self.request.id,
            client_id=client_id,
            error=str(e)
        )
        
        return {
            "error": str(e),
            "client_id": client_id,
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="health_check_workers")
def health_check_workers(self) -> Dict[str, Any]:
    """Periodic health check task for workers.
    
    Returns:
        Dictionary with health check results
    """
    try:
        logger.info(
            "Starting worker health check task",
            task_id=self.request.id
        )
        
        from ats_backend.workers.celery_app import task_monitor
        
        # Get worker statistics
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        # Determine health status
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
        
        # Check for stuck tasks (active for too long)
        active_task_data = active_tasks.get("active_tasks", {})
        for worker_name, tasks in active_task_data.items():
            for task in tasks:
                # This is a simplified check - in production you'd want to track task start times
                if len(tasks) > 10:  # Too many active tasks per worker
                    issues.append(f"Worker {worker_name} has {len(tasks)} active tasks")
        
        health_result = {
            "healthy": healthy,
            "status": "healthy" if healthy else "degraded",
            "issues": issues,
            "summary": {
                "workers": worker_stats.get("total_workers", 0),
                "active_tasks": active_tasks.get("total_active", 0),
                "queued_tasks": total_queued
            },
            "timestamp": logger.info.__self__.timestamp if hasattr(logger.info.__self__, 'timestamp') else None,
            "task_id": self.request.id
        }
        
        if not healthy:
            logger.warning(
                "Worker health check detected issues",
                task_id=self.request.id,
                issues=issues
            )
        else:
            logger.info(
                "Worker health check passed",
                task_id=self.request.id
            )
        
        return health_result
        
    except Exception as e:
        logger.error(
            "Worker health check task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "healthy": False,
            "status": "error",
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(bind=True, name="monitor_system_performance")
def monitor_system_performance(self) -> Dict[str, Any]:
    """Monitor system performance metrics.
    
    Returns:
        Dictionary with performance metrics
    """
    try:
        logger.info(
            "Starting system performance monitoring task",
            task_id=self.request.id
        )
        
        import psutil
        from datetime import datetime, timedelta
        from ats_backend.workers.celery_app import task_monitor
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get Celery metrics
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        # Calculate performance indicators
        performance_metrics = {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free_gb": disk.free / (1024**3)
            },
            "celery": {
                "total_workers": worker_stats.get("total_workers", 0),
                "active_tasks": active_tasks.get("total_active", 0),
                "queued_tasks": queue_info.get("total_queued", 0),
                "queue_breakdown": queue_info.get("queues", {})
            },
            "alerts": [],
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.request.id
        }
        
        # Generate alerts based on thresholds
        if cpu_percent > 80:
            performance_metrics["alerts"].append(f"High CPU usage: {cpu_percent}%")
        
        if memory.percent > 85:
            performance_metrics["alerts"].append(f"High memory usage: {memory.percent}%")
        
        if (disk.used / disk.total) * 100 > 90:
            performance_metrics["alerts"].append(f"High disk usage: {(disk.used / disk.total) * 100:.1f}%")
        
        if queue_info.get("total_queued", 0) > 50:
            performance_metrics["alerts"].append(f"High queue backlog: {queue_info.get('total_queued', 0)} tasks")
        
        if worker_stats.get("total_workers", 0) == 0:
            performance_metrics["alerts"].append("No workers available")
        
        # Log alerts if any
        if performance_metrics["alerts"]:
            logger.warning(
                "System performance alerts detected",
                task_id=self.request.id,
                alerts=performance_metrics["alerts"]
            )
        else:
            logger.info(
                "System performance monitoring completed - no alerts",
                task_id=self.request.id
            )
        
        return performance_metrics
        
    except Exception as e:
        logger.error(
            "System performance monitoring task failed",
            task_id=self.request.id,
            error=str(e)
        )
        
        return {
            "error": str(e),
            "task_id": self.request.id
        }