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


@celery_app.task(bind=True, base=EmailProcessingTask, name="monitor_system_performance")
def monitor_system_performance(self):
    """Monitor system performance and trigger alerts."""
    try:
        from ats_backend.core.observability import observability_system
        from ats_backend.core.alerts import alert_manager
        import asyncio
        
        logger.info("Starting system performance monitoring")
        
        # Run async monitoring
        async def run_monitoring():
            # Collect performance metrics
            performance_metrics = await observability_system.collect_performance_metrics()
            cost_metrics = await observability_system.collect_cost_metrics()
            
            # Check for alerts
            new_alerts = await observability_system.check_alerts()
            
            # Process alerts through alert manager
            notification_results = []
            for alert in new_alerts:
                result = await alert_manager.process_alert(alert)
                notification_results.append(result)
            
            return {
                "performance_metrics_count": len(performance_metrics),
                "cost_metrics": cost_metrics.to_dict(),
                "new_alerts": len(new_alerts),
                "notifications_sent": sum(notification_results),
                "alerts": [alert.to_dict() for alert in new_alerts]
            }
        
        # Execute monitoring
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(run_monitoring())
        except RuntimeError:
            result = asyncio.run(run_monitoring())
        
        logger.info(
            "System performance monitoring completed",
            new_alerts=result["new_alerts"],
            notifications_sent=result["notifications_sent"]
        )
        
        return result
        
    except Exception as e:
        logger.error("System performance monitoring failed", error=str(e))
        raise


@celery_app.task(bind=True, base=EmailProcessingTask, name="health_check_workers")
def health_check_workers(self):
    """Perform comprehensive health check of workers and system."""
    try:
        from ats_backend.core.health import health_checker
        import asyncio
        
        logger.info("Starting worker health check")
        
        # Run async health check
        async def run_health_check():
            health_report = await health_checker.run_all_checks()
            return health_report
        
        # Execute health check
        try:
            loop = asyncio.get_event_loop()
            health_report = loop.run_until_complete(run_health_check())
        except RuntimeError:
            health_report = asyncio.run(run_health_check())
        
        # Determine if system is healthy
        healthy = health_report["overall_status"] in ["healthy", "degraded"]
        
        logger.info(
            "Worker health check completed",
            overall_status=health_report["overall_status"],
            healthy_checks=health_report["summary"]["healthy_checks"],
            total_checks=health_report["summary"]["total_checks"]
        )
        
        return {
            "healthy": healthy,
            "overall_status": health_report["overall_status"],
            "summary": health_report["summary"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Worker health check failed", error=str(e))
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(bind=True, base=EmailProcessingTask, name="monitor_queue_health")
def monitor_queue_health(self):
    """Monitor queue health and alert on issues."""
    try:
        from ats_backend.workers.celery_app import task_monitor
        from ats_backend.core.observability import observability_system
        from ats_backend.core.alerts import alert_manager, Alert, AlertSeverity
        import asyncio
        
        logger.info("Starting queue health monitoring")
        
        # Get queue information
        queue_info = task_monitor.get_queue_lengths()
        worker_stats = task_monitor.get_worker_stats()
        
        issues = []
        alerts_triggered = []
        
        # Check for queue issues
        total_queued = queue_info.get("total_queued", 0)
        total_workers = worker_stats.get("total_workers", 0)
        
        if total_workers == 0:
            alert = Alert(
                name="no_workers_available",
                condition="worker_count < 1",
                severity=AlertSeverity.CRITICAL,
                threshold=1.0,
                current_value=0.0,
                triggered_at=datetime.utcnow(),
                message="No Celery workers are available",
                details={"worker_stats": worker_stats, "queue_info": queue_info}
            )
            alerts_triggered.append(alert)
            issues.append("No workers available")
        
        if total_queued > 500:
            alert = Alert(
                name="critical_queue_depth",
                condition="queue_depth > 500",
                severity=AlertSeverity.CRITICAL,
                threshold=500.0,
                current_value=total_queued,
                triggered_at=datetime.utcnow(),
                message=f"Critical queue backlog: {total_queued} tasks",
                details={"queue_info": queue_info}
            )
            alerts_triggered.append(alert)
            issues.append(f"Critical queue backlog: {total_queued}")
        elif total_queued > 100:
            alert = Alert(
                name="high_queue_depth",
                condition="queue_depth > 100",
                severity=AlertSeverity.WARNING,
                threshold=100.0,
                current_value=total_queued,
                triggered_at=datetime.utcnow(),
                message=f"High queue backlog: {total_queued} tasks",
                details={"queue_info": queue_info}
            )
            alerts_triggered.append(alert)
            issues.append(f"High queue backlog: {total_queued}")
        
        # Process alerts
        async def process_alerts():
            notification_results = []
            for alert in alerts_triggered:
                result = await alert_manager.process_alert(alert)
                notification_results.append(result)
            return notification_results
        
        if alerts_triggered:
            try:
                loop = asyncio.get_event_loop()
                notification_results = loop.run_until_complete(process_alerts())
            except RuntimeError:
                notification_results = asyncio.run(process_alerts())
        else:
            notification_results = []
        
        logger.info(
            "Queue health monitoring completed",
            total_queued=total_queued,
            total_workers=total_workers,
            issues_count=len(issues),
            alerts_triggered=len(alerts_triggered),
            notifications_sent=sum(notification_results)
        )
        
        return {
            "healthy": len(issues) == 0,
            "total_queued": total_queued,
            "total_workers": total_workers,
            "issues": issues,
            "alerts_triggered": len(alerts_triggered),
            "notifications_sent": sum(notification_results),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Queue health monitoring failed", error=str(e))
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(bind=True, base=EmailProcessingTask, name="cleanup_stale_tasks")
def cleanup_stale_tasks(self):
    """Clean up stale tasks and metrics."""
    try:
        from ats_backend.core.metrics import metrics_collector
        from datetime import timedelta
        
        logger.info("Starting stale task cleanup")
        
        # Clean up old metrics (older than 24 hours)
        metrics_collector.cleanup_old_metrics(timedelta(hours=24))
        
        # TODO: Add cleanup for stale Celery tasks
        # This would involve checking for tasks that have been running too long
        # and potentially terminating them
        
        logger.info("Stale task cleanup completed")
        
        return {
            "success": True,
            "message": "Stale task cleanup completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Stale task cleanup failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(bind=True, base=EmailProcessingTask, name="collect_performance_metrics")
def collect_performance_metrics(self, operation: Optional[str] = None):
    """Collect and store performance metrics."""
    try:
        from ats_backend.core.observability import observability_system
        import asyncio
        
        logger.info("Starting performance metrics collection", operation=operation)
        
        # Run async metrics collection
        async def run_collection():
            performance_metrics = await observability_system.collect_performance_metrics(operation)
            cost_metrics = await observability_system.collect_cost_metrics()
            
            return {
                "performance_metrics": {op: perf.to_dict() for op, perf in performance_metrics.items()},
                "cost_metrics": cost_metrics.to_dict()
            }
        
        # Execute collection
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(run_collection())
        except RuntimeError:
            result = asyncio.run(run_collection())
        
        logger.info(
            "Performance metrics collection completed",
            operation=operation,
            metrics_count=len(result["performance_metrics"])
        )
        
        return result
        
    except Exception as e:
        logger.error("Performance metrics collection failed", error=str(e))
        raise


@celery_app.task(bind=True, base=EmailProcessingTask, name="generate_observability_report")
def generate_observability_report(self, hours_back: int = 24):
    """Generate comprehensive observability report."""
    try:
        from ats_backend.core.observability import observability_system
        import asyncio
        
        logger.info("Starting observability report generation", hours_back=hours_back)
        
        # Run async report generation
        async def generate_report():
            # Get 60-second diagnostic
            diagnostic_data = await observability_system.get_60_second_diagnostic()
            
            # Get historical trends
            trends = observability_system.get_historical_trends(hours_back)
            
            # Get current performance and cost metrics
            performance_metrics = await observability_system.collect_performance_metrics()
            cost_metrics = await observability_system.collect_cost_metrics()
            
            return {
                "report_timestamp": datetime.utcnow().isoformat(),
                "time_range_hours": hours_back,
                "current_status": {
                    "overall_status": diagnostic_data.get("overall_status", "unknown"),
                    "system_health": diagnostic_data.get("system_health", {}),
                    "active_alerts": diagnostic_data.get("active_alerts", []),
                    "alert_count": diagnostic_data.get("alert_count", 0)
                },
                "performance_summary": {
                    op: {
                        "p95_ms": perf.p95_ms,
                        "error_rate": perf.error_rate,
                        "throughput_per_second": perf.throughput_per_second,
                        "count": perf.count
                    }
                    for op, perf in performance_metrics.items()
                },
                "cost_summary": {
                    "current_hourly_cost": cost_metrics.total_estimated_cost_per_hour,
                    "projected_daily_cost": cost_metrics.total_estimated_cost_per_hour * 24,
                    "projected_monthly_cost": cost_metrics.total_estimated_cost_per_hour * 24 * 30,
                    "resource_efficiency": cost_metrics.resource_efficiency
                },
                "trends": trends,
                "recommendations": _generate_recommendations(diagnostic_data, performance_metrics, cost_metrics, trends)
            }
        
        # Execute report generation
        try:
            loop = asyncio.get_event_loop()
            report = loop.run_until_complete(generate_report())
        except RuntimeError:
            report = asyncio.run(generate_report())
        
        logger.info(
            "Observability report generated",
            hours_back=hours_back,
            overall_status=report["current_status"]["overall_status"],
            alert_count=report["current_status"]["alert_count"]
        )
        
        return report
        
    except Exception as e:
        logger.error("Observability report generation failed", error=str(e))
        raise


def _generate_recommendations(diagnostic_data, performance_metrics, cost_metrics, trends):
    """Generate recommendations based on observability data."""
    recommendations = []
    
    # Check for performance issues
    for operation, perf in performance_metrics.items():
        if perf.p95_ms > 5000:  # 5 seconds
            recommendations.append({
                "type": "performance",
                "priority": "high",
                "message": f"{operation} P95 response time is {perf.p95_ms:.1f}ms, consider optimization",
                "operation": operation
            })
        
        if perf.error_rate > 0.05:  # 5%
            recommendations.append({
                "type": "reliability",
                "priority": "critical",
                "message": f"{operation} error rate is {perf.error_rate*100:.1f}%, investigate immediately",
                "operation": operation
            })
    
    # Check for cost issues
    if cost_metrics.total_estimated_cost_per_hour > 10.0:
        recommendations.append({
            "type": "cost",
            "priority": "medium",
            "message": f"Estimated cost is ${cost_metrics.total_estimated_cost_per_hour:.2f}/hour, consider optimization"
        })
    
    # Check for resource efficiency
    if cost_metrics.resource_efficiency > 0.8:
        recommendations.append({
            "type": "efficiency",
            "priority": "low",
            "message": "Resource efficiency is low, consider scaling down or optimizing resource usage"
        })
    
    # Check system health
    system_health = diagnostic_data.get("system_health", {})
    if system_health.get("overall_status") == "unhealthy":
        recommendations.append({
            "type": "health",
            "priority": "critical",
            "message": "System health is unhealthy, immediate attention required"
        })
    
    # Check active alerts
    alert_count = diagnostic_data.get("alert_count", 0)
    if alert_count > 0:
        recommendations.append({
            "type": "alerts",
            "priority": "high",
            "message": f"{alert_count} active alerts require attention"
        })
    
    return recommendations