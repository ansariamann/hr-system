"""Comprehensive error handling system with retry mechanisms and fallback strategies."""

import asyncio
import functools
import time
import random
from typing import Any, Callable, Dict, List, Optional, Type, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager
import structlog

from .config import settings
from .logging import get_logger, error_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification and routing."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE = "database"
    EXTERNAL_SERVICE = "external_service"
    NETWORK = "network"
    PARSING = "parsing"
    FILE_SYSTEM = "file_system"
    CONFIGURATION = "configuration"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"


@dataclass
class ErrorContext:
    """Context information for error handling and logging."""
    operation: str
    component: str
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


class ATSError(Exception):
    """Base exception class for ATS system errors."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context
        self.original_error = original_error
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging and API responses."""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "context": {
                "operation": self.context.operation if self.context else None,
                "component": self.context.component if self.context else None,
                "user_id": self.context.user_id if self.context else None,
                "client_id": self.context.client_id if self.context else None,
                "request_id": self.context.request_id if self.context else None,
                "additional_data": self.context.additional_data if self.context else None,
            },
            "original_error": str(self.original_error) if self.original_error else None,
            "original_error_type": type(self.original_error).__name__ if self.original_error else None,
        }


class ValidationError(ATSError):
    """Error for data validation failures."""
    
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(
            message,
            ErrorCategory.VALIDATION,
            ErrorSeverity.LOW,
            **kwargs
        )
        self.field = field
        self.value = value


class AuthenticationError(ATSError):
    """Error for authentication failures."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message,
            ErrorCategory.AUTHENTICATION,
            ErrorSeverity.HIGH,
            **kwargs
        )


class AuthorizationError(ATSError):
    """Error for authorization failures."""
    
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message,
            ErrorCategory.AUTHORIZATION,
            ErrorSeverity.HIGH,
            **kwargs
        )


class DatabaseError(ATSError):
    """Error for database operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            ErrorCategory.DATABASE,
            ErrorSeverity.HIGH,
            **kwargs
        )


class ExternalServiceError(ATSError):
    """Error for external service failures."""
    
    def __init__(self, message: str, service_name: str = None, **kwargs):
        super().__init__(
            message,
            ErrorCategory.EXTERNAL_SERVICE,
            ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.service_name = service_name


class ParsingError(ATSError):
    """Error for document parsing failures."""
    
    def __init__(self, message: str, file_path: str = None, **kwargs):
        super().__init__(
            message,
            ErrorCategory.PARSING,
            ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.file_path = file_path


class ConfigurationError(ATSError):
    """Error for configuration issues."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            ErrorCategory.CONFIGURATION,
            ErrorSeverity.CRITICAL,
            **kwargs
        )


class RetryableError(ATSError):
    """Error that can be retried."""
    
    def __init__(self, message: str, retry_after: Optional[float] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class CircuitBreakerError(ATSError):
    """Error when circuit breaker is open."""
    
    def __init__(self, message: str = "Circuit breaker is open", **kwargs):
        super().__init__(
            message,
            ErrorCategory.SYSTEM,
            ErrorSeverity.HIGH,
            **kwargs
        )


class ErrorHandler:
    """Centralized error handling with logging and metrics."""
    
    def __init__(self):
        self.logger = get_logger("error_handler")
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        notify: bool = True
    ) -> ATSError:
        """Handle and classify errors with appropriate logging.
        
        Args:
            error: The original exception
            context: Error context information
            notify: Whether to send notifications for critical errors
            
        Returns:
            Classified ATS error
        """
        # Convert to ATS error if not already
        if isinstance(error, ATSError):
            ats_error = error
        else:
            ats_error = self._classify_error(error, context)
        
        # Log the error with appropriate level
        self._log_error(ats_error)
        
        # Send notifications for critical errors
        if notify and ats_error.severity == ErrorSeverity.CRITICAL:
            self._notify_critical_error(ats_error)
        
        return ats_error
    
    def _classify_error(self, error: Exception, context: Optional[ErrorContext]) -> ATSError:
        """Classify generic exceptions into ATS errors."""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Database errors
        if "database" in error_message.lower() or "sql" in error_message.lower():
            return DatabaseError(
                f"Database operation failed: {error_message}",
                context=context,
                original_error=error
            )
        
        # Network/connection errors
        if any(keyword in error_message.lower() for keyword in ["connection", "timeout", "network"]):
            return ExternalServiceError(
                f"Network operation failed: {error_message}",
                context=context,
                original_error=error
            )
        
        # File system errors
        if any(keyword in error_message.lower() for keyword in ["file", "directory", "permission"]):
            return ATSError(
                f"File system operation failed: {error_message}",
                ErrorCategory.FILE_SYSTEM,
                ErrorSeverity.MEDIUM,
                context=context,
                original_error=error
            )
        
        # Validation errors
        if "validation" in error_message.lower() or error_type in ["ValueError", "TypeError"]:
            return ValidationError(
                f"Validation failed: {error_message}",
                context=context,
                original_error=error
            )
        
        # Default classification
        return ATSError(
            f"Unexpected error: {error_message}",
            ErrorCategory.SYSTEM,
            ErrorSeverity.MEDIUM,
            context=context,
            original_error=error
        )
    
    def _log_error(self, error: ATSError):
        """Log error with appropriate level and context."""
        log_data = error.to_dict()
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical("Critical error occurred", **log_data)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error("High severity error occurred", **log_data)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning("Medium severity error occurred", **log_data)
        else:
            self.logger.info("Low severity error occurred", **log_data)
    
    def _notify_critical_error(self, error: ATSError):
        """Send notifications for critical errors."""
        # In a real implementation, this would send alerts via email, Slack, etc.
        self.logger.critical(
            "CRITICAL ERROR NOTIFICATION",
            error_message=error.message,
            category=error.category.value,
            timestamp=error.timestamp.isoformat(),
            context=error.context.to_dict() if error.context else None
        )


class RetryManager:
    """Manages retry logic with exponential backoff and jitter."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.logger = get_logger("retry_manager")
    
    def retry(
        self,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        context: Optional[ErrorContext] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            config: Retry configuration (optional)
            context: Error context for logging
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        retry_config = config or self.config
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(
                        "Retry succeeded",
                        attempt=attempt + 1,
                        max_attempts=retry_config.max_attempts,
                        operation=context.operation if context else "unknown",
                        component=context.component if context else "unknown"
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not isinstance(e, retry_config.retryable_exceptions):
                    self.logger.warning(
                        "Non-retryable exception encountered",
                        exception_type=type(e).__name__,
                        exception_message=str(e),
                        attempt=attempt + 1,
                        operation=context.operation if context else "unknown"
                    )
                    raise
                
                # Don't sleep on the last attempt
                if attempt < retry_config.max_attempts - 1:
                    delay = self._calculate_delay(attempt, retry_config)
                    
                    self.logger.warning(
                        "Retry attempt failed, waiting before next attempt",
                        attempt=attempt + 1,
                        max_attempts=retry_config.max_attempts,
                        delay_seconds=delay,
                        exception_type=type(e).__name__,
                        exception_message=str(e),
                        operation=context.operation if context else "unknown"
                    )
                    
                    time.sleep(delay)
                else:
                    self.logger.error(
                        "All retry attempts failed",
                        max_attempts=retry_config.max_attempts,
                        final_exception_type=type(e).__name__,
                        final_exception_message=str(e),
                        operation=context.operation if context else "unknown"
                    )
        
        # All retries failed
        raise last_exception
    
    async def async_retry(
        self,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        context: Optional[ErrorContext] = None,
        **kwargs
    ) -> Any:
        """Execute async function with retry logic."""
        retry_config = config or self.config
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(
                        "Async retry succeeded",
                        attempt=attempt + 1,
                        max_attempts=retry_config.max_attempts,
                        operation=context.operation if context else "unknown"
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not isinstance(e, retry_config.retryable_exceptions):
                    raise
                
                if attempt < retry_config.max_attempts - 1:
                    delay = self._calculate_delay(attempt, retry_config)
                    
                    self.logger.warning(
                        "Async retry attempt failed",
                        attempt=attempt + 1,
                        max_attempts=retry_config.max_attempts,
                        delay_seconds=delay,
                        exception_type=type(e).__name__,
                        operation=context.operation if context else "unknown"
                    )
                    
                    await asyncio.sleep(delay)
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for retry attempt with exponential backoff and jitter."""
        delay = min(
            config.base_delay * (config.exponential_base ** attempt),
            config.max_delay
        )
        
        if config.jitter:
            # Add random jitter (±25% of delay)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class CircuitBreaker:
    """Circuit breaker pattern implementation for external service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
        self.logger = get_logger("circuit_breaker")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
                self.logger.info("Circuit breaker transitioning to half-open state")
            else:
                raise CircuitBreakerError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == "half-open":
            self.state = "closed"
            self.logger.info("Circuit breaker reset to closed state")
        
        self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.logger.warning(
                "Circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )


class FallbackManager:
    """Manages fallback strategies for critical operations."""
    
    def __init__(self):
        self.logger = get_logger("fallback_manager")
    
    def with_fallback(
        self,
        primary_func: Callable,
        fallback_func: Callable,
        context: Optional[ErrorContext] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute primary function with fallback on failure.
        
        Args:
            primary_func: Primary function to execute
            fallback_func: Fallback function if primary fails
            context: Error context for logging
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Result from primary or fallback function
        """
        try:
            return primary_func(*args, **kwargs)
            
        except Exception as e:
            self.logger.warning(
                "Primary function failed, executing fallback",
                primary_function=primary_func.__name__,
                fallback_function=fallback_func.__name__,
                error=str(e),
                error_type=type(e).__name__,
                operation=context.operation if context else "unknown"
            )
            
            try:
                result = fallback_func(*args, **kwargs)
                
                self.logger.info(
                    "Fallback function succeeded",
                    fallback_function=fallback_func.__name__,
                    operation=context.operation if context else "unknown"
                )
                
                return result
                
            except Exception as fallback_error:
                self.logger.error(
                    "Both primary and fallback functions failed",
                    primary_function=primary_func.__name__,
                    fallback_function=fallback_func.__name__,
                    primary_error=str(e),
                    fallback_error=str(fallback_error),
                    operation=context.operation if context else "unknown"
                )
                
                # Re-raise the original error
                raise e


# Decorator functions for easy integration
def with_error_handling(
    category: ErrorCategory = ErrorCategory.SYSTEM,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    component: str = None
):
    """Decorator for automatic error handling."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = ErrorContext(
                operation=func.__name__,
                component=component or func.__module__
            )
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler = ErrorHandler()
                ats_error = error_handler.handle_error(e, context)
                raise ats_error
        
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Decorator for automatic retry logic."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                retryable_exceptions=retryable_exceptions
            )
            
            context = ErrorContext(
                operation=func.__name__,
                component=func.__module__
            )
            
            retry_manager = RetryManager(config)
            return retry_manager.retry(func, *args, context=context, **kwargs)
        
        return wrapper
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
):
    """Decorator for circuit breaker protection."""
    circuit_breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Global instances
error_handler = ErrorHandler()
retry_manager = RetryManager()
fallback_manager = FallbackManager()


# Configuration validation functions
def validate_database_config() -> bool:
    """Validate database configuration."""
    try:
        required_fields = ['postgres_host', 'postgres_port', 'postgres_db', 'postgres_user']
        
        for field in required_fields:
            value = getattr(settings, field, None)
            if not value:
                raise ConfigurationError(f"Missing required database configuration: {field}")
        
        # Test database URL construction
        db_url = settings.database_url
        if not db_url or not db_url.startswith('postgresql://'):
            raise ConfigurationError("Invalid database URL format")
        
        logger.info("Database configuration validated successfully")
        return True
        
    except Exception as e:
        logger.error("Database configuration validation failed", error=str(e))
        raise ConfigurationError(f"Database configuration validation failed: {str(e)}")


def validate_redis_config() -> bool:
    """Validate Redis configuration."""
    try:
        if not settings.redis_host:
            raise ConfigurationError("Missing Redis host configuration")
        
        if not isinstance(settings.redis_port, int) or settings.redis_port <= 0:
            raise ConfigurationError("Invalid Redis port configuration")
        
        # Test Redis URL construction
        redis_url = settings.redis_url
        if not redis_url or not redis_url.startswith('redis://'):
            raise ConfigurationError("Invalid Redis URL format")
        
        logger.info("Redis configuration validated successfully")
        return True
        
    except Exception as e:
        logger.error("Redis configuration validation failed", error=str(e))
        raise ConfigurationError(f"Redis configuration validation failed: {str(e)}")


def validate_api_config() -> bool:
    """Validate API configuration."""
    try:
        if not settings.secret_key or settings.secret_key == "dev-secret-key":
            if settings.environment == "production":
                raise ConfigurationError("Production environment requires secure secret key")
        
        if settings.access_token_expire_minutes <= 0:
            raise ConfigurationError("Invalid token expiration time")
        
        if not settings.api_host:
            raise ConfigurationError("Missing API host configuration")
        
        if not isinstance(settings.api_port, int) or settings.api_port <= 0:
            raise ConfigurationError("Invalid API port configuration")
        
        logger.info("API configuration validated successfully")
        return True
        
    except Exception as e:
        logger.error("API configuration validation failed", error=str(e))
        raise ConfigurationError(f"API configuration validation failed: {str(e)}")


def validate_email_config() -> bool:
    """Validate email processing configuration."""
    try:
        if not settings.email_storage_path:
            raise ConfigurationError("Missing email storage path configuration")
        
        if settings.max_attachment_size_mb <= 0:
            raise ConfigurationError("Invalid maximum attachment size")
        
        if not settings.supported_file_extensions:
            raise ConfigurationError("No supported file extensions configured")
        
        # Validate file extensions format
        for ext in settings.supported_file_extensions:
            if not ext.startswith('.'):
                raise ConfigurationError(f"Invalid file extension format: {ext}")
        
        logger.info("Email configuration validated successfully")
        return True
        
    except Exception as e:
        logger.error("Email configuration validation failed", error=str(e))
        raise ConfigurationError(f"Email configuration validation failed: {str(e)}")


def validate_all_configurations() -> bool:
    """Validate all system configurations."""
    try:
        validate_database_config()
        validate_redis_config()
        validate_api_config()
        validate_email_config()
        
        logger.info("All configurations validated successfully")
        return True
        
    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(f"Configuration validation failed: {str(e)}")


# Startup health checks
def perform_startup_checks() -> Dict[str, bool]:
    """Perform comprehensive startup health checks."""
    checks = {}
    
    try:
        # Configuration validation
        checks['configuration'] = validate_all_configurations()
        
        # Database connectivity (would need actual database connection)
        checks['database'] = True  # Placeholder - would test actual connection
        
        # Redis connectivity (would need actual Redis connection)
        checks['redis'] = True  # Placeholder - would test actual connection
        
        # File system permissions
        import os
        try:
            os.makedirs(settings.email_storage_path, exist_ok=True)
            test_file = os.path.join(settings.email_storage_path, '.test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            checks['file_system'] = True
        except Exception as e:
            logger.error("File system check failed", error=str(e))
            checks['file_system'] = False
        
        # OCR availability
        try:
            import subprocess
            result = subprocess.run([settings.tesseract_cmd, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            checks['ocr'] = result.returncode == 0
        except Exception as e:
            logger.warning("OCR availability check failed", error=str(e))
            checks['ocr'] = False
        
        logger.info("Startup checks completed", checks=checks)
        return checks
        
    except Exception as e:
        logger.error("Startup checks failed", error=str(e))
        raise ConfigurationError(f"Startup checks failed: {str(e)}")