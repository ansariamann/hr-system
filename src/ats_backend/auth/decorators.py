"""Authorization decorators for API endpoints."""

from functools import wraps
from typing import Callable, Any
from uuid import UUID

from fastapi import HTTPException, status
import structlog

from .models import User

logger = structlog.get_logger(__name__)


def require_auth(func: Callable) -> Callable:
    """Decorator to require authentication for a function.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # This decorator is mainly for documentation purposes
        # The actual authentication is handled by FastAPI dependencies
        return await func(*args, **kwargs)
    
    return wrapper


def require_client_access(allowed_client_ids: list[UUID] = None):
    """Decorator to require access to specific clients.
    
    Args:
        allowed_client_ids: List of client IDs that are allowed access
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs (should be injected by dependency)
            current_user = kwargs.get('current_user')
            
            if not isinstance(current_user, User):
                logger.error("No current user found in function arguments")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if allowed_client_ids and current_user.client_id not in allowed_client_ids:
                logger.warning("Client access denied",
                              user_id=str(current_user.id),
                              user_client_id=str(current_user.client_id),
                              allowed_clients=[str(cid) for cid in allowed_client_ids])
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this resource"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_active_user(func: Callable) -> Callable:
    """Decorator to require an active user.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get('current_user')
        
        if not isinstance(current_user, User):
            logger.error("No current user found in function arguments")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        if not current_user.is_active:
            logger.warning("Inactive user access attempt", user_id=str(current_user.id))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper