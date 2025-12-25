"""Security middleware for abuse protection."""

from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from ats_backend.security.abuse_protection import abuse_protection

logger = structlog.get_logger(__name__)


class AbuseProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware for global abuse protection and rate limiting."""
    
    def __init__(self, app, skip_paths: list = None):
        """Initialize abuse protection middleware.
        
        Args:
            app: FastAPI application
            skip_paths: List of paths to skip protection for
        """
        super().__init__(app)
        self.skip_paths = skip_paths or [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/health",
            "/metrics"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with abuse protection.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint
            
        Returns:
            Response from next middleware/endpoint
        """
        # Skip protection for certain paths
        if self._should_skip_protection(request.url.path):
            return await call_next(request)
        
        try:
            # Apply global rate limiting based on IP
            ip_address = request.client.host if request.client else "unknown"
            
            # Check general API rate limiting
            await abuse_protection.rate_limiter.check_rate_limit(
                key=ip_address,
                limit_type="api_requests",
                identifier=f"IP {ip_address}",
                request=request
            )
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions (like rate limit exceeded)
            raise
        except Exception as e:
            logger.error(
                "Abuse protection middleware error",
                error=str(e),
                path=request.url.path,
                method=request.method
            )
            # Continue processing - don't block on middleware errors
            return await call_next(request)
    
    def _should_skip_protection(self, path: str) -> bool:
        """Check if protection should be skipped for this path.
        
        Args:
            path: Request path
            
        Returns:
            True if protection should be skipped
        """
        return any(path.startswith(skip_path) for skip_path in self.skip_paths)


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware for input sanitization and validation."""
    
    def __init__(self, app, skip_paths: list = None):
        """Initialize input sanitization middleware.
        
        Args:
            app: FastAPI application
            skip_paths: List of paths to skip sanitization for
        """
        super().__init__(app)
        self.skip_paths = skip_paths or [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/health",
            "/metrics"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with input sanitization.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint
            
        Returns:
            Response from next middleware/endpoint
        """
        # Skip sanitization for certain paths
        if self._should_skip_sanitization(request.url.path):
            return await call_next(request)
        
        try:
            # Validate query parameters for dangerous patterns
            if request.query_params:
                for key, value in request.query_params.items():
                    try:
                        # Validate query parameter values
                        abuse_protection.input_validator.validate_text_input(
                            value, f"query_param_{key}", request
                        )
                    except HTTPException as e:
                        logger.warning(
                            "Dangerous query parameter detected",
                            key=key,
                            value=value[:100],  # Truncate for logging
                            path=request.url.path
                        )
                        raise e
            
            # Validate path parameters for path traversal
            path = str(request.url.path)
            try:
                abuse_protection.input_validator.validate_text_input(
                    path, "url_path", request
                )
            except HTTPException as e:
                logger.warning(
                    "Dangerous URL path detected",
                    path=path,
                    method=request.method
                )
                raise e
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions (like validation errors)
            raise
        except Exception as e:
            logger.error(
                "Input sanitization middleware error",
                error=str(e),
                path=request.url.path,
                method=request.method
            )
            # Continue processing - don't block on middleware errors
            return await call_next(request)
    
    def _should_skip_sanitization(self, path: str) -> bool:
        """Check if sanitization should be skipped for this path.
        
        Args:
            path: Request path
            
        Returns:
            True if sanitization should be skipped
        """
        return any(path.startswith(skip_path) for skip_path in self.skip_paths)