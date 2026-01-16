"""FastAPI application with comprehensive error handling and startup validation."""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
import structlog
import time
import asyncio
import signal
import sys

from ats_backend.core.config import settings
from ats_backend.core.database import get_db
from ats_backend.core.logging import configure_logging, system_logger, performance_logger, error_logger
from ats_backend.core.metrics import metrics_middleware
from ats_backend.core.error_handling import (
    ATSError, ErrorHandler, error_handler, with_error_handling,
    ValidationError, AuthenticationError, DatabaseError,
    ErrorCategory, ErrorSeverity, ErrorContext
)
from ats_backend.core.startup import initialize_application, shutdown_application, validate_startup_environment
from ats_backend.auth.middleware import AuthenticationMiddleware
from ats_backend.security.middleware import AbuseProtectionMiddleware, InputSanitizationMiddleware
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User, Token, UserResponse
from ats_backend.auth.utils import authenticate_user, create_access_token
from ats_backend.models.client import Client
from ats_backend.services.client_service import ClientService
from ats_backend.api.email import router as email_router
from ats_backend.api.monitoring import router as monitoring_router
from ats_backend.api.candidates import router as candidates_router
from ats_backend.api.applications import router as applications_router
from ats_backend.api.security import router as security_router
from ats_backend.api.sse import router as sse_router
from ats_backend.api.observability import router as observability_router

# Configure logging
configure_logging()
logger = structlog.get_logger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive error handling and conversion."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except ATSError as e:
            # ATS errors are already properly formatted
            error_logger.log_error_with_context(
                error=e,
                operation="http_request",
                request_data={
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers)
                }
            )
            
            return JSONResponse(
                status_code=self._get_http_status_code(e),
                content={
                    "error": {
                        "message": e.message,
                        "category": e.category.value,
                        "severity": e.severity.value,
                        "timestamp": e.timestamp.isoformat()
                    }
                }
            )
            
        except HTTPException as e:
            # FastAPI HTTP exceptions
            return JSONResponse(
                status_code=e.status_code,
                content={"error": {"message": e.detail}}
            )
            
        except Exception as e:
            # Unexpected errors
            context = ErrorContext(
                operation="http_request",
                component="api",
                additional_data={
                    "method": request.method,
                    "url": str(request.url)
                }
            )
            
            ats_error = error_handler.handle_error(e, context)
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Internal server error",
                        "category": ats_error.category.value,
                        "severity": ats_error.severity.value,
                        "timestamp": ats_error.timestamp.isoformat()
                    }
                }
            )
    
    def _get_http_status_code(self, error: ATSError) -> int:
        """Map ATS error categories to HTTP status codes."""
        status_map = {
            ErrorCategory.VALIDATION: 400,
            ErrorCategory.AUTHENTICATION: 401,
            ErrorCategory.AUTHORIZATION: 403,
            ErrorCategory.DATABASE: 500,
            ErrorCategory.EXTERNAL_SERVICE: 502,
            ErrorCategory.NETWORK: 503,
            ErrorCategory.PARSING: 422,
            ErrorCategory.FILE_SYSTEM: 500,
            ErrorCategory.CONFIGURATION: 500,
            ErrorCategory.BUSINESS_LOGIC: 400,
            ErrorCategory.SYSTEM: 500,
        }
        
        return status_map.get(error.category, 500)
class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging and metrics."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract client info if available
        client_id = getattr(request.state, 'client_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        # Log request start
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            client_id=str(client_id) if client_id else None,
            user_id=str(user_id) if user_id else None
        )
        
        # Start metrics tracking
        finish_metrics = metrics_middleware.track_request(
            request_path=request.url.path,
            method=request.method,
            client_id=str(client_id) if client_id else None
        )
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Log successful response
            logger.info(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time_seconds=round(process_time, 3),
                client_id=str(client_id) if client_id else None,
                user_id=str(user_id) if user_id else None
            )
            
            # Finish metrics tracking
            finish_metrics(response.status_code)
            
            # Add performance headers
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Calculate response time for errors
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                method=request.method,
                url=str(request.url),
                error=str(e),
                error_type=type(e).__name__,
                process_time_seconds=round(process_time, 3),
                client_id=str(client_id) if client_id else None,
                user_id=str(user_id) if user_id else None
            )
            
            # Finish metrics tracking with error status
            finish_metrics(500)
            
            raise


# Global shutdown flag
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# Create FastAPI app
app = FastAPI(
    title="ATS Backend API",
    description="Multi-tenant Applicant Tracking System with comprehensive error handling and monitoring",
    version="0.1.0"
)

# Add middleware in correct order (last added = first executed)
# Inner layers (executed closest to the application)
app.add_middleware(LoggingMiddleware)

# Security Layer (executed before logging, closest to app in security chain)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(AbuseProtectionMiddleware)
app.add_middleware(InputSanitizationMiddleware)

# Outer Layers (executed first on request, last on response)
# Error Handling must wrap everything to catch middleware errors
app.add_middleware(ErrorHandlingMiddleware)

# CORS must be outermost to ensure headers are added to ALL responses (including errors)
# Using explicit origins list for reliable preflight handling
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routers
app.include_router(email_router)
# ... (omitted lines)

@app.post("/auth/login", response_model=Token)
@with_error_handling(component="authentication")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token with comprehensive error handling and security features."""
    print(f"DEBUG: Login Request for {form_data.username} / {form_data.password}")
    from ats_backend.auth.utils import authenticate_user
    
    context = ErrorContext(
        operation="user_login",
        component="authentication",
        additional_data={"email": form_data.username}
    )
    
    # Extract client information for security logging
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    try:
        with performance_logger.log_operation_time(
            "user_login",
            email=form_data.username
        ):
            user = authenticate_user(
                db, 
                form_data.username, 
                form_data.password,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not user:
                print(f"DEBUG: Login failed for {form_data.username}")
                logger.warning("Login failed", email=form_data.username)
                raise AuthenticationError(
                    "Incorrect email or password",
                    context=context
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
            
            logger.info(
                "User logged in successfully",
                user_id=str(user.id),
                email=user.email,
                client_id=str(user.client_id)
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.access_token_expire_minutes * 60
            }
            
    except ATSError:
        raise
    except Exception as e:
        raise error_handler.handle_error(e, context)


@app.get("/auth/me", response_model=UserResponse)
@with_error_handling(component="authentication")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information with error handling."""
    logger.info(
        "User info requested",
        user_id=str(current_user.id),
        email=current_user.email
    )
    return current_user


@app.get("/auth/client")
@with_error_handling(component="authentication")
async def get_current_client_info(
    current_client: Client = Depends(get_current_client)
):
    """Get current client information with error handling."""
    logger.info(
        "Client info requested",
        client_id=str(current_client.id),
        client_name=current_client.name
    )
    return {
        "id": current_client.id,
        "name": current_client.name,
        "email_domain": current_client.email_domain,
        "created_at": current_client.created_at,
        "updated_at": current_client.updated_at
    }


@app.get("/clients/stats")
@with_error_handling(component="client_service")
async def get_client_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics for current client with comprehensive error handling."""
    context = ErrorContext(
        operation="get_client_stats",
        component="client_service",
        user_id=str(current_user.id),
        client_id=str(current_user.client_id)
    )
    
    try:
        with performance_logger.log_operation_time(
            "get_client_stats",
            user_id=str(current_user.id),
            client_id=str(current_user.client_id)
        ):
            stats = ClientService.get_client_stats(db, current_user.client_id)
            
            logger.info(
                "Client stats retrieved",
                user_id=str(current_user.id),
                client_id=str(current_user.client_id),
                stats_keys=list(stats.keys()) if isinstance(stats, dict) else None
            )
            
            return stats
            
    except Exception as e:
        raise error_handler.handle_error(e, context)


@app.get("/protected")
@with_error_handling(component="api")
async def protected_endpoint(
    current_user: User = Depends(get_current_user)
):
    """Example protected endpoint with error handling."""
    logger.info(
        "Protected endpoint accessed",
        user_id=str(current_user.id),
        client_id=str(current_user.client_id)
    )
    return {
        "message": "This is a protected endpoint",
        "user_id": str(current_user.id),
        "client_id": str(current_user.client_id)
    }


# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Application startup event with comprehensive initialization."""
    try:
        # Validate startup environment
        validate_startup_environment()
        
        # Initialize system with comprehensive checks
        initialization_success = await initialize_application()
        
        if not initialization_success:
            logger.critical("System initialization failed, shutting down")
            sys.exit(1)
        
        system_logger.log_system_startup(
            "fastapi_server",
            host=settings.api_host,
            port=settings.api_port,
            environment=settings.environment,
            initialization_success=initialization_success
        )
        
        logger.info(
            "ATS Backend API started successfully",
            version="0.1.0",
            environment=settings.environment,
            host=settings.api_host,
            port=settings.api_port
        )
        
    except Exception as e:
        logger.critical(
            "Failed to start ATS Backend API",
            error=str(e),
            error_type=type(e).__name__
        )
        sys.exit(1)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event with graceful cleanup."""
    try:
        await shutdown_application()
        
        system_logger.log_system_shutdown(
            "fastapi_server",
            environment=settings.environment
        )
        
        logger.info(
            "ATS Backend API shutdown completed",
            environment=settings.environment
        )
        
    except Exception as e:
        logger.error(
            "Error during ATS Backend API shutdown",
            error=str(e),
            error_type=type(e).__name__
        )


async def run_with_graceful_shutdown():
    """Run the application with graceful shutdown handling."""
    import uvicorn
    
    # Create server configuration
    config = uvicorn.Config(
        "ats_backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,  # Disable reload in production
        log_config=None  # Use our custom logging
    )
    
    server = uvicorn.Server(config)
    
    # Start server in background task
    server_task = asyncio.create_task(server.serve())
    
    # Wait for shutdown signal
    await shutdown_event.wait()
    
    # Graceful shutdown
    logger.info("Initiating graceful shutdown")
    server.should_exit = True
    
    # Wait for server to finish
    await server_task
    
    logger.info("Server shutdown completed")


if __name__ == "__main__":
    try:
        asyncio.run(run_with_graceful_shutdown())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.critical("Unexpected error during server execution", error=str(e))
        sys.exit(1)
# Force reload
