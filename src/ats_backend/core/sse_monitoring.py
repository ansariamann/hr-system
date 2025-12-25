"""SSE monitoring and alerting for sub-second latency guarantees."""

import asyncio
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque
import structlog

from .config import settings

logger = structlog.get_logger(__name__)


@dataclass
class LatencyMetric:
    """Represents a latency measurement."""
    timestamp: float
    latency_ms: float
    event_type: str
    tenant_id: str


@dataclass
class SSEMonitoringMetrics:
    """SSE monitoring metrics and thresholds."""
    
    # Latency tracking
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=1000))
    latency_threshold_ms: float = 1000.0  # 1 second threshold
    
    # Performance counters
    events_published_total: int = 0
    events_delivered_total: int = 0
    events_failed_total: int = 0
    connections_established_total: int = 0
    connections_dropped_total: int = 0
    reconnections_total: int = 0
    
    # Current state
    active_connections: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Alert state
    latency_violations: int = 0
    last_alert_time: float = 0.0
    alert_cooldown_seconds: float = 300.0  # 5 minutes


class SSEMonitor:
    """Monitors SSE performance and triggers alerts for latency violations."""
    
    def __init__(self):
        self.metrics = SSEMonitoringMetrics()
        self.alert_callbacks = []
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
    
    def start_monitoring(self):
        """Start the monitoring background task."""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("SSE monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring background task."""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            logger.info("SSE monitoring stopped")
    
    def record_event_published(self, event_type: str, tenant_id: str):
        """Record an event publication."""
        self.metrics.events_published_total += 1
        
        # Record timestamp for latency tracking
        timestamp = time.time()
        # Store in a way that can be matched with delivery
        # This is simplified - in production you'd want more sophisticated tracking
    
    def record_event_delivered(
        self, 
        event_type: str, 
        tenant_id: str, 
        publish_timestamp: float
    ):
        """Record an event delivery and calculate latency."""
        self.metrics.events_delivered_total += 1
        
        # Calculate latency
        delivery_timestamp = time.time()
        latency_ms = (delivery_timestamp - publish_timestamp) * 1000
        
        # Record latency sample
        latency_metric = LatencyMetric(
            timestamp=delivery_timestamp,
            latency_ms=latency_ms,
            event_type=event_type,
            tenant_id=tenant_id
        )
        self.metrics.latency_samples.append(latency_metric)
        
        # Check for latency violation
        if latency_ms > self.metrics.latency_threshold_ms:
            self.metrics.latency_violations += 1
            self._trigger_latency_alert(latency_metric)
        
        logger.debug(
            "SSE event delivered",
            event_type=event_type,
            tenant_id=tenant_id,
            latency_ms=latency_ms
        )
    
    def record_event_failed(self, event_type: str, tenant_id: str, error: str):
        """Record a failed event delivery."""
        self.metrics.events_failed_total += 1
        
        logger.warning(
            "SSE event delivery failed",
            event_type=event_type,
            tenant_id=tenant_id,
            error=error
        )
    
    def record_connection_established(self, tenant_id: str, user_id: str):
        """Record a new SSE connection."""
        self.metrics.connections_established_total += 1
        self.metrics.active_connections += 1
        
        logger.info(
            "SSE connection established",
            tenant_id=tenant_id,
            user_id=user_id,
            active_connections=self.metrics.active_connections
        )
    
    def record_connection_dropped(self, tenant_id: str, user_id: str, reason: str):
        """Record a dropped SSE connection."""
        self.metrics.connections_dropped_total += 1
        self.metrics.active_connections = max(0, self.metrics.active_connections - 1)
        
        logger.info(
            "SSE connection dropped",
            tenant_id=tenant_id,
            user_id=user_id,
            reason=reason,
            active_connections=self.metrics.active_connections
        )
    
    def record_reconnection(self, tenant_id: str, user_id: str, missed_events: int):
        """Record a client reconnection."""
        self.metrics.reconnections_total += 1
        
        logger.info(
            "SSE reconnection handled",
            tenant_id=tenant_id,
            user_id=user_id,
            missed_events=missed_events
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current monitoring metrics."""
        # Calculate latency percentiles
        if self.metrics.latency_samples:
            latencies = [sample.latency_ms for sample in self.metrics.latency_samples]
            latencies.sort()
            
            n = len(latencies)
            self.metrics.average_latency_ms = sum(latencies) / n
            self.metrics.p95_latency_ms = latencies[int(n * 0.95)] if n > 0 else 0
            self.metrics.p99_latency_ms = latencies[int(n * 0.99)] if n > 0 else 0
        
        return {
            "events_published_total": self.metrics.events_published_total,
            "events_delivered_total": self.metrics.events_delivered_total,
            "events_failed_total": self.metrics.events_failed_total,
            "connections_established_total": self.metrics.connections_established_total,
            "connections_dropped_total": self.metrics.connections_dropped_total,
            "reconnections_total": self.metrics.reconnections_total,
            "active_connections": self.metrics.active_connections,
            "average_latency_ms": round(self.metrics.average_latency_ms, 2),
            "p95_latency_ms": round(self.metrics.p95_latency_ms, 2),
            "p99_latency_ms": round(self.metrics.p99_latency_ms, 2),
            "latency_violations": self.metrics.latency_violations,
            "latency_threshold_ms": self.metrics.latency_threshold_ms,
            "monitoring_active": self.monitoring_active
        }
    
    def add_alert_callback(self, callback):
        """Add a callback function for alerts."""
        self.alert_callbacks.append(callback)
    
    def _trigger_latency_alert(self, latency_metric: LatencyMetric):
        """Trigger an alert for latency violation."""
        current_time = time.time()
        
        # Check alert cooldown
        if current_time - self.metrics.last_alert_time < self.metrics.alert_cooldown_seconds:
            return
        
        self.metrics.last_alert_time = current_time
        
        alert_data = {
            "alert_type": "sse_latency_violation",
            "severity": "warning" if latency_metric.latency_ms < 2000 else "critical",
            "message": f"SSE latency violation: {latency_metric.latency_ms:.2f}ms > {self.metrics.latency_threshold_ms}ms",
            "event_type": latency_metric.event_type,
            "tenant_id": latency_metric.tenant_id,
            "latency_ms": latency_metric.latency_ms,
            "threshold_ms": self.metrics.latency_threshold_ms,
            "timestamp": latency_metric.timestamp
        }
        
        logger.warning(
            "SSE latency violation detected",
            **alert_data
        )
        
        # Trigger alert callbacks
        for callback in self.alert_callbacks:
            try:
                asyncio.create_task(callback(alert_data))
            except Exception as e:
                logger.error(
                    "Alert callback failed",
                    callback=str(callback),
                    error=str(e)
                )
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Perform periodic monitoring tasks
                await self._check_system_health()
                await self._cleanup_old_samples()
                
                # Sleep for monitoring interval
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Monitoring loop error", error=str(e))
                await asyncio.sleep(10)
    
    async def _check_system_health(self):
        """Check overall SSE system health."""
        metrics = self.get_metrics()
        
        # Check for high failure rate
        total_events = metrics["events_published_total"]
        failed_events = metrics["events_failed_total"]
        
        if total_events > 100:  # Only check after some activity
            failure_rate = failed_events / total_events
            if failure_rate > 0.05:  # 5% failure rate threshold
                logger.warning(
                    "High SSE failure rate detected",
                    failure_rate=failure_rate,
                    total_events=total_events,
                    failed_events=failed_events
                )
        
        # Check for high average latency
        if metrics["average_latency_ms"] > self.metrics.latency_threshold_ms * 0.8:
            logger.warning(
                "High average SSE latency detected",
                average_latency_ms=metrics["average_latency_ms"],
                threshold_ms=self.metrics.latency_threshold_ms
            )
    
    async def _cleanup_old_samples(self):
        """Clean up old latency samples."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # Keep samples for 1 hour
        
        # Remove old samples
        while (self.metrics.latency_samples and 
               self.metrics.latency_samples[0].timestamp < cutoff_time):
            self.metrics.latency_samples.popleft()


# Global SSE monitor instance
sse_monitor = SSEMonitor()


async def default_alert_handler(alert_data: Dict[str, Any]):
    """Default alert handler that logs alerts."""
    logger.warning(
        "SSE Alert",
        alert_type=alert_data["alert_type"],
        severity=alert_data["severity"],
        message=alert_data["message"]
    )


# Register default alert handler
sse_monitor.add_alert_callback(default_alert_handler)