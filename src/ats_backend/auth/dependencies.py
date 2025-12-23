"""FastAPI dependencies for authentication and authorization."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.core.session_context import set_client_context
from ats_backend.models.client import Client
from .models import User
from .utils import verify_token, get_user_by_id

logger = structlog.get_logger(__name__)

# Security scheme - make it optional for some endpoints
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
        
    Returns:
        Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        logger.warning("No credentials provided")
        raise credentials_exception
    
    try:
        token_data = verify_token(credentials.credentials)
        if token_data is None or token_data.user_id is None:
            logger.warning("Invalid token data")
            raise credentials_exception
            
        user = get_user_by_id(db, token_data.user_id)
        if user is None:
            logger.warning("User not found", user_id=str(token_data.user_id))
            raise credentials_exception
            
        # Set client context for RLS
        if user.client_id:
            set_client_context(db, user.client_id)
            logger.debug("Client context set for user", 
                        user_id=str(user.id), 
                        client_id=str(user.client_id))
        
        return user
        
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise credentials_exception


async def get_current_client(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Client:
    """Get current client from authenticated user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Current client
        
    Raises:
        HTTPException: If client not found
    """
    client = db.query(Client).filter(Client.id == current_user.client_id).first()
    
    if not client:
        logger.error("Client not found", client_id=str(current_user.client_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    return client


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.
    
    Args:
        credentials: HTTP Bearer credentials (optional)
        db: Database session
        
    Returns:
        Current user if authenticated, None otherwise
    """
    if not credentials:
        return None
        
    try:
        token_data = verify_token(credentials.credentials)
        if token_data is None or token_data.user_id is None:
            return None
            
        user = get_user_by_id(db, token_data.user_id)
        if user and user.client_id:
            set_client_context(db, user.client_id)
            
        return user
        
    except Exception as e:
        logger.debug("Optional authentication failed", error=str(e))
        return None


def require_client_access(required_client_id: UUID):
    """Dependency factory to require access to a specific client.
    
    Args:
        required_client_id: Client ID that user must have access to
        
    Returns:
        Dependency function
    """
    async def check_client_access(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.client_id != required_client_id:
            logger.warning("Client access denied", 
                          user_id=str(current_user.id),
                          user_client_id=str(current_user.client_id),
                          required_client_id=str(required_client_id))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        return current_user
    
    return check_client_access