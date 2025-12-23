"""FastAPI application with authentication middleware."""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import structlog

from ats_backend.core.config import settings
from ats_backend.core.database import get_db
from ats_backend.auth.middleware import AuthenticationMiddleware
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User, Token, UserResponse
from ats_backend.auth.utils import authenticate_user, create_access_token
from ats_backend.models.client import Client
from ats_backend.services.client_service import ClientService
from ats_backend.api.email import router as email_router

logger = structlog.get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ATS Backend API",
    description="Multi-tenant Applicant Tracking System",
    version="0.1.0"
)

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Include API routers
app.include_router(email_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ats-backend"}


@app.post("/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        logger.warning("Login failed", email=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "client_id": str(user.client_id),
            "email": user.email
        },
        expires_delta=access_token_expires
    )
    
    logger.info("User logged in", user_id=str(user.id), email=user.email)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60
    }


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information."""
    return current_user


@app.get("/auth/client")
async def get_current_client_info(
    current_client: Client = Depends(get_current_client)
):
    """Get current client information."""
    return {
        "id": current_client.id,
        "name": current_client.name,
        "email_domain": current_client.email_domain,
        "created_at": current_client.created_at,
        "updated_at": current_client.updated_at
    }


@app.get("/clients/stats")
async def get_client_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics for current client."""
    stats = ClientService.get_client_stats(db, current_user.client_id)
    return stats


# Protected endpoint example
@app.get("/protected")
async def protected_endpoint(
    current_user: User = Depends(get_current_user)
):
    """Example protected endpoint."""
    return {
        "message": "This is a protected endpoint",
        "user_id": str(current_user.id),
        "client_id": str(current_user.client_id)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ats_backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )