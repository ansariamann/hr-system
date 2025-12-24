"""Structured logging configuration."""

import logging
import sys
import time
from typing import Any, Dict, Optional
from datetime import datetime
from contextlib import contextmanager

import structlog
from structlog.stdlib import LoggerFactory

from .config import settings


def configure_logging() -> None:
    """Configure structured logging for the application."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.environment == "production"
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.log_level == "DEBUG" else logging.WARNING
    )
    
    # Configure additional loggers for comprehensive system logging
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("email").setLevel(logging.INFO)
    logging.getLogger("resume_processing").setLevel(logging.INFO)
    logging.getLogger("audit").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


def log_request_context(
    client_id: str = None,
    user_id: str = None,
    request_id: str = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Create logging context for requests.
    
    Args:
        client_id: Client identifier
        user_id: User identifier  
        request_id: Request identifier
        **kwargs: Additional context
        
    Returns:
        Context dictionary for logging
    """
    context = {}
    
    if client_id:
        context["client_id"] = client_id
    if user_id:
        context["user_id"] = user_id
    if request_id:
        context["request_id"] = request_id
    
    context.update(kwargs)
    return context


class PerformanceLogger:
    """Logger for tracking performance metrics."""
    
    def __init__(self, logger_name: str = "performance"):
        self.logger = get_logger(logger_name)
    
    @contextmanager
    def log_operation_time(
        self,
        operation: str,
        **context: Any
    ):
        """Context manager to log operation execution time.
        
        Args:
            operation: Name of the operation being timed
            **context: Additional context for logging
        """
        start_time = time.time()
        start_timestamp = datetime.utcnow()
        
        self.logger.info(
            "Operation started",
            operation=operation,
            start_time=start_timestamp.isoformat(),
            **context
        )
        
        try:
            yield
            
            end_time = time.time()
            duration = end_time - start_time
            
            self.logger.info(
                "Operation completed",
                operation=operation,
                duration_seconds=round(duration, 3),
                start_time=start_timestamp.isoformat(),
                end_time=datetime.utcnow().isoformat(),
                **context
            )
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            self.logger.error(
                "Operation failed",
                operation=operation,
                duration_seconds=round(duration, 3),
                start_time=start_timestamp.isoformat(),
                end_time=datetime.utcnow().isoformat(),
                error=str(e),
                error_type=type(e).__name__,
                **context
            )
            raise
    
    def log_processing_metrics(
        self,
        operation: str,
        items_processed: int,
        duration_seconds: float,
        success_count: int = None,
        error_count: int = None,
        **context: Any
    ):
        """Log processing metrics for batch operations.
        
        Args:
            operation: Name of the operation
            items_processed: Total number of items processed
            duration_seconds: Total processing time
            success_count: Number of successful items (optional)
            error_count: Number of failed items (optional)
            **context: Additional context
        """
        throughput = items_processed / duration_seconds if duration_seconds > 0 else 0
        
        self.logger.info(
            "Processing metrics",
            operation=operation,
            items_processed=items_processed,
            duration_seconds=round(duration_seconds, 3),
            throughput_per_second=round(throughput, 2),
            success_count=success_count,
            error_count=error_count,
            **context
        )


class SystemLogger:
    """Logger for system-wide events and monitoring."""
    
    def __init__(self, logger_name: str = "system"):
        self.logger = get_logger(logger_name)
    
    def log_system_startup(self, component: str, **context: Any):
        """Log system component startup."""
        self.logger.info(
            "System component started",
            component=component,
            timestamp=datetime.utcnow().isoformat(),
            **context
        )
    
    def log_system_shutdown(self, component: str, **context: Any):
        """Log system component shutdown."""
        self.logger.info(
            "System component shutdown",
            component=component,
            timestamp=datetime.utcnow().isoformat(),
            **context
        )
    
    def log_health_check(
        self,
        component: str,
        healthy: bool,
        details: Dict[str, Any] = None,
        **context: Any
    ):
        """Log health check results."""
        log_level = "info" if healthy else "warning"
        
        getattr(self.logger, log_level)(
            "Health check completed",
            component=component,
            healthy=healthy,
            details=details or {},
            timestamp=datetime.utcnow().isoformat(),
            **context
        )
    
    def log_resource_usage(
        self,
        cpu_percent: float,
        memory_percent: float,
        disk_percent: float,
        **context: Any
    ):
        """Log system resource usage."""
        self.logger.info(
            "System resource usage",
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
            timestamp=datetime.utcnow().isoformat(),
            **context
        )
    
    def log_queue_metrics(
        self,
        queue_name: str,
        queue_length: int,
        processing_rate: float = None,
        **context: Any
    ):
        """Log queue metrics."""
        self.logger.info(
            "Queue metrics",
            queue_name=queue_name,
            queue_length=queue_length,
            processing_rate=processing_rate,
            timestamp=datetime.utcnow().isoformat(),
            **context
        )


class ErrorLogger:
    """Logger for detailed error tracking and debugging."""
    
    def __init__(self, logger_name: str = "error"):
        self.logger = get_logger(logger_name)
    
    def log_error_with_context(
        self,
        error: Exception,
        operation: str,
        user_id: str = None,
        client_id: str = None,
        request_data: Dict[str, Any] = None,
        **context: Any
    ):
        """Log error with comprehensive context for debugging.
        
        Args:
            error: The exception that occurred
            operation: Name of the operation that failed
            user_id: User ID if applicable
            client_id: Client ID if applicable
            request_data: Request data that caused the error
            **context: Additional context
        """
        self.logger.error(
            "Detailed error occurred",
            operation=operation,
            error=str(error),
            error_type=type(error).__name__,
            user_id=user_id,
            client_id=client_id,
            request_data=request_data,
            timestamp=datetime.utcnow().isoformat(),
            **context
        )
    
    def log_validation_error(
        self,
        field: str,
        value: Any,
        error_message: str,
        **context: Any
    ):
        """Log validation errors with field details."""
        self.logger.warning(
            "Validation error",
            field=field,
            value=str(value)[:100],  # Truncate long values
            error_message=error_message,
            timestamp=datetime.utcnow().isoformat(),
            **context
        )
    
    def log_security_event(
        self,
        event_type: str,
        user_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        details: Dict[str, Any] = None,
        **context: Any
    ):
        """Log security-related events."""
        self.logger.warning(
            "Security event",
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            timestamp=datetime.utcnow().isoformat(),
            **context
        )


# Global logger instances
performance_logger = PerformanceLogger()
system_logger = SystemLogger()
error_logger = ErrorLogger()