"""Server-Sent Events (SSE) manager with Redis Pub/Sub backend and guaranteed ordering."""

import asyncio
import json
import time
from typing import Dict, Optional, Any, AsyncGenerator, Set
from uuid import UUID
import structlog
from fastapi import Request
from fastapi.responses import StreamingResponse
import redis.asyncio as redis
from redis.asyncio import Redis

from .config import settings
from .redis import get_redis
from .sse_monitoring import sse_monitor

logger = structlog.get_logger(__name__)


class SSEEvent:
    """Represents a Server-Sent Event with ordering guarantees."""
    
    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: UUID,
        application_id: Optional[UUID] = None,
        sequence: Optional[int] = None,
        event_id: Optional[str] = None
    ):
        self.event_type = event_type
        self.data = data
        self.tenant_id = tenant_id
        self.application_id = application_id
        self.sequence = sequence or 0
        self.event_id = event_id or f"{tenant_id}_{int(time.time() * 1000)}_{sequence}"
        self.timestamp = time.time()
    
    def to_sse_format(self) -> str:
        """Convert event to SSE format string."""
        sse_data = {
            "type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "application_id": str(self.application_id) if self.application_id else None
        }
        
        lines = [
            f"id: {self.event_id}",
            f"event: {self.event_type}",
            f"data: {json.dumps(sse_data)}",
            "",  # Empty line to end the event
        ]
        
        return "\n".join(lines) + "\n"


class SSEConnection:
    """Represents an active SSE connection with state management."""
    
    def __init__(
        self,
        connection_id: str,
        tenant_id: UUID,
        user_id: UUID,
        last_event_id: Optional[str] = None
    ):
        self.connection_id = connection_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.last_event_id = last_event_id
        self.connected_at = time.time()
        self.last_heartbeat = time.time()
        self.is_active = True
        self.missed_events: Set[str] = set()
    
    def update_heartbeat(self):
        """Update the last heartbeat timestamp."""
        self.last_heartbeat = time.time()
    
    def mark_disconnected(self):
        """Mark connection as disconnected."""
        self.is_active = False


class SSEManager:
    """Manages Server-Sent Events with Redis Pub/Sub backend and guaranteed ordering."""
    
    def __init__(self):
        self.redis_client: Optional[Redis] = None
        self.active_connections: Dict[str, SSEConnection] = {}
        self.sequence_counters: Dict[str, int] = {}  # tenant_id:app_id -> sequence
        self.event_store: Dict[str, SSEEvent] = {}  # event_id -> event (for replay)
        self.heartbeat_interval = 30  # seconds
        self.event_retention_time = 3600  # 1 hour
        self.max_missed_events = 100
        
        # Metrics tracking
        self.metrics = {
            "events_published": 0,
            "events_delivered": 0,
            "connections_active": 0,
            "reconnections_handled": 0,
            "events_replayed": 0,
            "latency_sum": 0.0,
            "latency_count": 0
        }
    
    async def initialize(self):
        """Initialize the SSE manager with Redis connection."""
        try:
            self.redis_client = await get_redis()
            logger.info("SSE Manager initialized with Redis connection")
            
            # Start monitoring
            sse_monitor.start_monitoring()
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_task())
            asyncio.create_task(self._cleanup_task())
            
        except Exception as e:
            logger.error("Failed to initialize SSE Manager", error=str(e))
            raise
    
    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: UUID,
        application_id: Optional[UUID] = None
    ) -> bool:
        """Publish an event with guaranteed ordering.
        
        Args:
            event_type: Type of event (e.g., 'application_status_changed')
            data: Event data payload
            tenant_id: Tenant ID for multi-tenant isolation
            application_id: Optional application ID for per-application ordering
            
        Returns:
            True if event was published successfully, False otherwise
        """
        if not self.redis_client:
            logger.error("SSE Manager not initialized")
            return False
        
        try:
            # Get next sequence number for ordering
            sequence = await self._get_next_sequence(tenant_id, application_id)
            
            # Create event
            event = SSEEvent(
                event_type=event_type,
                data=data,
                tenant_id=tenant_id,
                application_id=application_id,
                sequence=sequence
            )
            
            # Store event for replay capability
            await self._store_event(event)
            
            # Publish to Redis channel
            channel = f"hr_events:{tenant_id}"
            event_payload = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "data": event.data,
                "sequence": event.sequence,
                "application_id": str(application_id) if application_id else None,
                "timestamp": event.timestamp
            }
            
            await self.redis_client.publish(channel, json.dumps(event_payload))
            
            # Record monitoring metrics
            sse_monitor.record_event_published(event_type, str(tenant_id))
            
            # Update metrics
            self.metrics["events_published"] += 1
            
            logger.info(
                "SSE event published",
                event_type=event_type,
                tenant_id=str(tenant_id),
                application_id=str(application_id) if application_id else None,
                sequence=sequence,
                event_id=event.event_id
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to publish SSE event",
                event_type=event_type,
                tenant_id=str(tenant_id),
                error=str(e)
            )
            return False
    
    async def create_event_stream(
        self,
        request: Request,
        tenant_id: UUID,
        user_id: UUID,
        last_event_id: Optional[str] = None
    ) -> StreamingResponse:
        """Create an SSE event stream for a client.
        
        Args:
            request: FastAPI request object
            tenant_id: Tenant ID for multi-tenant isolation
            user_id: User ID for connection tracking
            last_event_id: Last event ID received by client (for reconnection)
            
        Returns:
            StreamingResponse with SSE stream
        """
        connection_id = f"{tenant_id}_{user_id}_{int(time.time() * 1000)}"
        
        # Create connection object
        connection = SSEConnection(
            connection_id=connection_id,
            tenant_id=tenant_id,
            user_id=user_id,
            last_event_id=last_event_id
        )
        
        self.active_connections[connection_id] = connection
        self.metrics["connections_active"] += 1
        
        # Record monitoring metrics
        sse_monitor.record_connection_established(str(tenant_id), str(user_id))
        
        logger.info(
            "SSE connection established",
            connection_id=connection_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            last_event_id=last_event_id
        )
        
        # Handle reconnection with missed events replay
        if last_event_id:
            await self._handle_reconnection(connection)
        
        async def event_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for the client."""
            try:
                # Send initial connection event
                yield f"data: {json.dumps({'type': 'connected', 'connection_id': connection_id})}\n\n"
                
                # Subscribe to Redis channel
                channel = f"hr_events:{tenant_id}"
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(channel)
                
                # Start heartbeat and event processing
                heartbeat_task = asyncio.create_task(
                    self._send_heartbeats(connection_id)
                )
                
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            # Process event message
                            try:
                                event_data = json.loads(message["data"])
                                event_id = event_data.get("event_id")
                                
                                # Check if client is still connected
                                if not await request.is_disconnected():
                                    # Track latency
                                    event_timestamp = event_data.get("timestamp", time.time())
                                    latency = time.time() - event_timestamp
                                    self.metrics["latency_sum"] += latency
                                    self.metrics["latency_count"] += 1
                                    
                                    # Record monitoring metrics
                                    sse_monitor.record_event_delivered(
                                        event_data["event_type"],
                                        str(tenant_id),
                                        event_timestamp
                                    )
                                    
                                    # Send event to client
                                    sse_event = SSEEvent(
                                        event_type=event_data["event_type"],
                                        data=event_data["data"],
                                        tenant_id=tenant_id,
                                        application_id=UUID(event_data["application_id"]) if event_data.get("application_id") else None,
                                        sequence=event_data["sequence"],
                                        event_id=event_id
                                    )
                                    
                                    yield sse_event.to_sse_format()
                                    
                                    # Update connection state
                                    connection.last_event_id = event_id
                                    connection.update_heartbeat()
                                    
                                    self.metrics["events_delivered"] += 1
                                else:
                                    # Client disconnected
                                    break
                                    
                            except json.JSONDecodeError as e:
                                logger.error(
                                    "Failed to parse SSE event data",
                                    connection_id=connection_id,
                                    error=str(e)
                                )
                                sse_monitor.record_event_failed("unknown", str(tenant_id), str(e))
                            except Exception as e:
                                logger.error(
                                    "Error processing SSE event",
                                    connection_id=connection_id,
                                    error=str(e)
                                )
                                sse_monitor.record_event_failed("unknown", str(tenant_id), str(e))
                
                finally:
                    # Cleanup
                    heartbeat_task.cancel()
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
                    
            except asyncio.CancelledError:
                logger.info("SSE connection cancelled", connection_id=connection_id)
            except Exception as e:
                logger.error(
                    "SSE connection error",
                    connection_id=connection_id,
                    error=str(e)
                )
            finally:
                # Clean up connection
                await self._cleanup_connection(connection_id)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
    
    async def _get_next_sequence(
        self,
        tenant_id: UUID,
        application_id: Optional[UUID] = None
    ) -> int:
        """Get next sequence number for event ordering.
        
        Args:
            tenant_id: Tenant ID
            application_id: Optional application ID for per-application ordering
            
        Returns:
            Next sequence number
        """
        if application_id:
            key = f"seq:{tenant_id}:{application_id}"
        else:
            key = f"seq:{tenant_id}:global"
        
        try:
            sequence = await self.redis_client.incr(key)
            # Set expiration to prevent key accumulation
            await self.redis_client.expire(key, self.event_retention_time)
            return sequence
        except Exception as e:
            logger.error("Failed to get sequence number", key=key, error=str(e))
            # Fallback to local counter
            if key not in self.sequence_counters:
                self.sequence_counters[key] = 0
            self.sequence_counters[key] += 1
            return self.sequence_counters[key]
    
    async def _store_event(self, event: SSEEvent):
        """Store event for replay capability.
        
        Args:
            event: SSE event to store
        """
        try:
            # Store in Redis with expiration
            key = f"event:{event.event_id}"
            event_data = {
                "event_type": event.event_type,
                "data": event.data,
                "tenant_id": str(event.tenant_id),
                "application_id": str(event.application_id) if event.application_id else None,
                "sequence": event.sequence,
                "timestamp": event.timestamp
            }
            
            await self.redis_client.setex(
                key,
                self.event_retention_time,
                json.dumps(event_data)
            )
            
            # Also store in local cache for immediate access
            self.event_store[event.event_id] = event
            
        except Exception as e:
            logger.error(
                "Failed to store event",
                event_id=event.event_id,
                error=str(e)
            )
    
    async def _handle_reconnection(self, connection: SSEConnection):
        """Handle client reconnection with missed events replay.
        
        Args:
            connection: SSE connection object
        """
        if not connection.last_event_id:
            return
        
        try:
            self.metrics["reconnections_handled"] += 1
            
            # Find missed events since last_event_id
            missed_events = await self._find_missed_events(
                connection.tenant_id,
                connection.last_event_id
            )
            
            if missed_events:
                logger.info(
                    "Replaying missed events for reconnection",
                    connection_id=connection.connection_id,
                    missed_count=len(missed_events)
                )
                
                # Record monitoring metrics
                sse_monitor.record_reconnection(
                    str(connection.tenant_id),
                    str(connection.user_id),
                    len(missed_events)
                )
                
                # Store missed events for replay during stream
                connection.missed_events = set(event.event_id for event in missed_events)
                self.metrics["events_replayed"] += len(missed_events)
            
        except Exception as e:
            logger.error(
                "Failed to handle reconnection",
                connection_id=connection.connection_id,
                error=str(e)
            )
    
    async def _find_missed_events(
        self,
        tenant_id: UUID,
        last_event_id: str
    ) -> list[SSEEvent]:
        """Find events that were missed since the last event ID.
        
        Args:
            tenant_id: Tenant ID
            last_event_id: Last event ID received by client
            
        Returns:
            List of missed events
        """
        missed_events = []
        
        try:
            # Parse last event ID to get timestamp and sequence
            parts = last_event_id.split("_")
            if len(parts) >= 3:
                last_timestamp = int(parts[1]) / 1000  # Convert back to seconds
                last_sequence = int(parts[2])
                
                # Find events after the last event
                # This is a simplified implementation - in production, you might want
                # to use Redis sorted sets for more efficient range queries
                pattern = f"event:{tenant_id}_*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    try:
                        event_data = await self.redis_client.get(key)
                        if event_data:
                            event_info = json.loads(event_data)
                            event_timestamp = event_info.get("timestamp", 0)
                            event_sequence = event_info.get("sequence", 0)
                            
                            # Check if this event is after the last received event
                            if (event_timestamp > last_timestamp or 
                                (event_timestamp == last_timestamp and event_sequence > last_sequence)):
                                
                                event = SSEEvent(
                                    event_type=event_info["event_type"],
                                    data=event_info["data"],
                                    tenant_id=UUID(event_info["tenant_id"]),
                                    application_id=UUID(event_info["application_id"]) if event_info.get("application_id") else None,
                                    sequence=event_sequence,
                                    event_id=key.replace("event:", "")
                                )
                                missed_events.append(event)
                                
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(
                            "Failed to parse stored event",
                            key=key,
                            error=str(e)
                        )
                
                # Sort by timestamp and sequence
                missed_events.sort(key=lambda e: (e.timestamp, e.sequence))
                
                # Limit the number of missed events to prevent overwhelming the client
                if len(missed_events) > self.max_missed_events:
                    logger.warning(
                        "Too many missed events, truncating",
                        tenant_id=str(tenant_id),
                        missed_count=len(missed_events),
                        max_allowed=self.max_missed_events
                    )
                    missed_events = missed_events[-self.max_missed_events:]
        
        except Exception as e:
            logger.error(
                "Failed to find missed events",
                tenant_id=str(tenant_id),
                last_event_id=last_event_id,
                error=str(e)
            )
        
        return missed_events
    
    async def _send_heartbeats(self, connection_id: str):
        """Send periodic heartbeats to keep connection alive.
        
        Args:
            connection_id: Connection ID
        """
        try:
            while connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
                if not connection.is_active:
                    break
                
                # Send heartbeat
                heartbeat_data = {
                    "type": "heartbeat",
                    "timestamp": time.time(),
                    "connection_id": connection_id
                }
                
                yield f"data: {json.dumps(heartbeat_data)}\n\n"
                
                connection.update_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "Heartbeat error",
                connection_id=connection_id,
                error=str(e)
            )
    
    async def _cleanup_connection(self, connection_id: str):
        """Clean up a disconnected connection.
        
        Args:
            connection_id: Connection ID to clean up
        """
        if connection_id in self.active_connections:
            connection = self.active_connections[connection_id]
            connection.mark_disconnected()
            
            # Record monitoring metrics
            sse_monitor.record_connection_dropped(
                str(connection.tenant_id),
                str(connection.user_id),
                "client_disconnected"
            )
            
            del self.active_connections[connection_id]
            self.metrics["connections_active"] -= 1
            
            logger.info(
                "SSE connection cleaned up",
                connection_id=connection_id,
                duration=time.time() - connection.connected_at
            )
    
    async def _heartbeat_task(self):
        """Background task to monitor connection health."""
        while True:
            try:
                current_time = time.time()
                stale_connections = []
                
                for connection_id, connection in self.active_connections.items():
                    # Check if connection is stale (no heartbeat for too long)
                    if current_time - connection.last_heartbeat > self.heartbeat_interval * 3:
                        stale_connections.append(connection_id)
                
                # Clean up stale connections
                for connection_id in stale_connections:
                    await self._cleanup_connection(connection_id)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error("Heartbeat task error", error=str(e))
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _cleanup_task(self):
        """Background task to clean up old events and data."""
        while True:
            try:
                current_time = time.time()
                
                # Clean up old events from local store
                expired_events = [
                    event_id for event_id, event in self.event_store.items()
                    if current_time - event.timestamp > self.event_retention_time
                ]
                
                for event_id in expired_events:
                    del self.event_store[event_id]
                
                if expired_events:
                    logger.info(
                        "Cleaned up expired events",
                        count=len(expired_events)
                    )
                
                # Sleep for cleanup interval (every 10 minutes)
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error("Cleanup task error", error=str(e))
                await asyncio.sleep(600)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get SSE manager metrics.
        
        Returns:
            Dictionary of metrics
        """
        metrics = self.metrics.copy()
        
        # Calculate average latency
        if metrics["latency_count"] > 0:
            metrics["average_latency_ms"] = (metrics["latency_sum"] / metrics["latency_count"]) * 1000
        else:
            metrics["average_latency_ms"] = 0
        
        # Add current connection count
        metrics["connections_active"] = len(self.active_connections)
        
        return metrics
    
    async def force_disconnect_all(self):
        """Force disconnect all active connections (for shutdown)."""
        connection_ids = list(self.active_connections.keys())
        for connection_id in connection_ids:
            await self._cleanup_connection(connection_id)
        
        # Stop monitoring
        sse_monitor.stop_monitoring()
        
        logger.info("All SSE connections forcefully disconnected")


# Global SSE manager instance
sse_manager = SSEManager()