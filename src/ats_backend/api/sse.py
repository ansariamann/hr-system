"""Server-Sent Events API endpoints for real-time updates."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.core.sse_manager import sse_manager
from ats_backend.core.error_handling import with_error_handling

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])


@router.get("/events")
@with_error_handling(component="sse")
async def stream_events(
    request: Request,
    last_event_id: Optional[str] = Query(None, description="Last event ID for reconnection"),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Stream real-time events via Server-Sent Events.
    
    Provides a persistent connection for real-time updates about applications,
    candidates, and other system events. Supports automatic reconnection
    with missed event replay.
    
    Args:
        request: FastAPI request object
        last_event_id: Last event ID received (for reconnection handling)
        current_user: Authenticated user
        current_client: User's client (tenant)
        
    Returns:
        StreamingResponse with SSE events
    """
    try:
        logger.info(
            "SSE stream requested",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            last_event_id=last_event_id
        )
        
        # Create event stream
        return await sse_manager.create_event_stream(
            request=request,
            tenant_id=current_client.id,
            user_id=current_user.id,
            last_event_id=last_event_id
        )
        
    except Exception as e:
        logger.error(
            "Failed to create SSE stream",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event stream: {str(e)}"
        )


@router.post("/test-event")
@with_error_handling(component="sse")
async def send_test_event(
    event_type: str = Query("test", description="Type of test event"),
    message: str = Query("Test message", description="Test message content"),
    application_id: Optional[UUID] = Query(None, description="Optional application ID"),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Send a test event for SSE functionality testing.
    
    This endpoint is useful for testing SSE connectivity and event delivery.
    In production, events would be triggered by actual system changes.
    
    Args:
        event_type: Type of test event
        message: Test message content
        application_id: Optional application ID for testing per-application ordering
        current_user: Authenticated user
        current_client: User's client (tenant)
        db: Database session
        
    Returns:
        Success confirmation
    """
    try:
        # Prepare test event data
        event_data = {
            "message": message,
            "user_id": str(current_user.id),
            "timestamp": "test_timestamp",
            "test": True
        }
        
        # Publish test event
        success = await sse_manager.publish_event(
            event_type=event_type,
            data=event_data,
            tenant_id=current_client.id,
            application_id=application_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to publish test event"
            )
        
        logger.info(
            "Test SSE event sent",
            event_type=event_type,
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            application_id=str(application_id) if application_id else None
        )
        
        return {
            "success": True,
            "message": "Test event sent successfully",
            "event_type": event_type,
            "client_id": str(current_client.id),
            "application_id": str(application_id) if application_id else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to send test event",
            event_type=event_type,
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test event: {str(e)}"
        )


@router.get("/metrics")
@with_error_handling(component="sse")
async def get_sse_metrics(
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get SSE system metrics and performance data.
    
    Returns metrics about SSE performance, connection counts, latency,
    and other operational data for monitoring and alerting.
    
    Args:
        current_user: Authenticated user
        current_client: User's client (tenant)
        
    Returns:
        SSE metrics dictionary
    """
    try:
        # Get SSE manager metrics
        sse_metrics = sse_manager.get_metrics()
        
        # Get monitoring metrics
        from ats_backend.core.sse_monitoring import sse_monitor
        monitoring_metrics = sse_monitor.get_metrics()
        
        # Combine metrics
        combined_metrics = {
            **sse_metrics,
            "monitoring": monitoring_metrics
        }
        
        logger.info(
            "SSE metrics requested",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            active_connections=combined_metrics.get("connections_active", 0)
        )
        
        return {
            "success": True,
            "metrics": combined_metrics,
            "client_id": str(current_client.id)
        }
        
    except Exception as e:
        logger.error(
            "Failed to get SSE metrics",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SSE metrics: {str(e)}"
        )


@router.get("/health")
@with_error_handling(component="sse")
async def sse_health_check(
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Check SSE system health and connectivity.
    
    Verifies that the SSE system is operational, Redis is connected,
    and the system can handle new connections.
    
    Args:
        current_user: Authenticated user
        current_client: User's client (tenant)
        
    Returns:
        Health status information
    """
    try:
        # Check if SSE manager is initialized
        if not sse_manager.redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SSE system not initialized"
            )
        
        # Test Redis connectivity
        try:
            await sse_manager.redis_client.ping()
            redis_healthy = True
        except Exception:
            redis_healthy = False
        
        # Get current metrics
        metrics = sse_manager.get_metrics()
        
        health_status = {
            "status": "healthy" if redis_healthy else "degraded",
            "redis_connected": redis_healthy,
            "active_connections": metrics.get("connections_active", 0),
            "events_published": metrics.get("events_published", 0),
            "events_delivered": metrics.get("events_delivered", 0),
            "average_latency_ms": metrics.get("average_latency_ms", 0),
            "client_id": str(current_client.id)
        }
        
        logger.info(
            "SSE health check performed",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            status=health_status["status"]
        )
        
        return health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "SSE health check failed",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SSE health check failed: {str(e)}"
        )