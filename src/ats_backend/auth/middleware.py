"""Authentication middleware for FastAPI."""

from typing import Callable
from uuid import UUID

from fastapi import Request, Response, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.core.session_context import set_client_context, clear_client_context
from .utils import verify_token, get_user_by_id

logger = structlog.get_logger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for handling authentication and client context."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication and client context.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint
            
        Returns:
            Response from next middleware/endpoint
        """
        # Skip authentication for certain paths
        if self._should_skip_auth(request.url.path):
            return await call_next(request)
        
        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)
        
        if not authorization or scheme.lower() != "bearer":
            # No authentication provided - continue without setting context
            logger.debug("No authentication provided", path=request.url.path)
            return await call_next(request)
        
        # Verify token and set client context
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            from .utils import verify_token
            token_data = await verify_token(token, db)
            if token_data and token_data.user_id:
                # Verify user exists and is active
                user = get_user_by_id(db, token_data.user_id)
                if user and user.is_active and user.client_id:
                    # Set client context for RLS
                    set_client_context(db, user.client_id)
                    
                    # Store user info in request state
                    request.state.current_user_id = user.id
                    request.state.current_client_id = user.client_id
                    
                    logger.info("AUTH_DEBUG: Client context set via middleware",
                               user_id=str(user.id),
                               client_id=str(user.client_id),
                               path=request.url.path)
                else:
                    logger.info("AUTH_DEBUG: Invalid or inactive user in middleware", 
                                 user_id=str(token_data.user_id) if token_data.user_id else None)
                    
        except Exception as e:
            logger.info("AUTH_DEBUG: Authentication middleware error", error=str(e))
            # Continue without authentication rather than failing
        finally:
            # Clean up database session
            try:
                db.close()
            except:
                pass
        
        # Process request
        response = await call_next(request)
        
        return response
    
    def _should_skip_auth(self, path: str) -> bool:
        """Check if authentication should be skipped for this path.
        
        Args:
            path: Request path
            
        Returns:
            True if authentication should be skipped
        """
        skip_paths = [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/health",
            "/auth/login",
            "/auth/register",
        ]
        
        return any(path.startswith(skip_path) for skip_path in skip_paths)


def get_current_user_from_request(request: Request) -> tuple[UUID, UUID]:
    """Extract current user and client IDs from request state.
    
    Args:
        request: FastAPI request
        
    Returns:
        Tuple of (user_id, client_id)
        
    Raises:
        HTTPException: If user not authenticated
    """
    user_id = getattr(request.state, 'current_user_id', None)
    client_id = getattr(request.state, 'current_client_id', None)
    
    if not user_id or not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return user_id, client_id