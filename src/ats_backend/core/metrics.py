"""Performance metrics tracking and monitoring system."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import time
import threading
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric point to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "labels": self.labels
        }


@dataclass
class ProcessingMetrics:
    """Metrics for processing operations."""
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    items_processed: int = 0
    success_count: int = 0
    error_count: int = 0
    total_size_bytes: int = 0
    client_id: Optional[str] = None
    user_id: Optional[str] = None
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def throughput_per_second(self) -> float:
        """Calculate throughput per second."""
        duration = self.duration_seconds
        return self.items_processed / duration if duration > 0 else 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.success_count + self.error_count
        return (self.success_count / total * 100) if total > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert processing metrics to dictionary."""
        return {
            "operation": self.operation,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "items_processed": self.items_processed,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "throughput_per_second": self.throughput_per_second,
            "total_size_bytes": self.total_size_bytes,
            "client_id": self.client_id,
            "user_id": self.user_id
        }


class MetricsCollector:
    """Thread-safe metrics collector."""
    
    def __init__(self, max_points_per_metric: int = 1000):
        self.max_points_per_metric = max_points_per_metric
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points_per_metric))
        self._processing_metrics: List[ProcessingMetrics] = []
        self._lock = threading.RLock()
    
    def record_metric(
        self,
        name: str,
        value: float,
        labels: Dict[str, str] = None,
        timestamp: datetime = None
    ):
        """Record a metric point.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels for the metric
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        
        with self._lock:
            self._metrics[name].append(point)
        
        logger.debug(
            "Metric recorded",
            metric_name=name,
            value=value,
            labels=labels,
            timestamp=timestamp.isoformat()
        )
    
    def start_processing_metrics(
        self,
        operation: str,
        client_id: str = None,
        user_id: str = None
    ) -> ProcessingMetrics:
        """Start tracking processing metrics.
        
        Args:
            operation: Name of the operation
            client_id: Client ID (optional)
            user_id: User ID (optional)
            
        Returns:
            ProcessingMetrics instance to track the operation
        """
        metrics = ProcessingMetrics(
            operation=operation,
            start_time=datetime.utcnow(),
            client_id=client_id,
            user_id=user_id
        )
        
        with self._lock:
            self._processing_metrics.append(metrics)
        
        logger.info(
            "Processing metrics started",
            operation=operation,
            client_id=client_id,
            user_id=user_id
        )
        
        return metrics
    
    def finish_processing_metrics(self, metrics: ProcessingMetrics):
        """Finish tracking processing metrics.
        
        Args:
            metrics: ProcessingMetrics instance to finish
        """
        metrics.end_time = datetime.utcnow()
        
        # Record individual metrics
        self.record_metric(
            f"processing.duration.{metrics.operation}",
            metrics.duration_seconds,
            {"client_id": metrics.client_id, "user_id": metrics.user_id}
        )
        
        self.record_metric(
            f"processing.throughput.{metrics.operation}",
            metrics.throughput_per_second,
            {"client_id": metrics.client_id, "user_id": metrics.user_id}
        )
        
        self.record_metric(
            f"processing.success_rate.{metrics.operation}",
            metrics.success_rate,
            {"client_id": metrics.client_id, "user_id": metrics.user_id}
        )
        
        logger.info(
            "Processing metrics completed",
            operation=metrics.operation,
            duration_seconds=metrics.duration_seconds,
            items_processed=metrics.items_processed,
            success_rate=metrics.success_rate,
            throughput_per_second=metrics.throughput_per_second,
            client_id=metrics.client_id,
            user_id=metrics.user_id
        )
    
    def get_metric_history(
        self,
        name: str,
        since: datetime = None,
        limit: int = None
    ) -> List[MetricPoint]:
        """Get metric history.
        
        Args:
            name: Metric name
            since: Only return points after this timestamp
            limit: Maximum number of points to return
            
        Returns:
            List of metric points
        """
        with self._lock:
            points = list(self._metrics.get(name, []))
        
        if since:
            points = [p for p in points if p.timestamp >= since]
        
        if limit:
            points = points[-limit:]
        
        return points
    
    def get_processing_metrics_history(
        self,
        operation: str = None,
        client_id: str = None,
        since: datetime = None,
        limit: int = None
    ) -> List[ProcessingMetrics]:
        """Get processing metrics history.
        
        Args:
            operation: Filter by operation name
            client_id: Filter by client ID
            since: Only return metrics after this timestamp
            limit: Maximum number of metrics to return
            
        Returns:
            List of processing metrics
        """
        with self._lock:
            metrics = list(self._processing_metrics)
        
        # Apply filters
        if operation:
            metrics = [m for m in metrics if m.operation == operation]
        
        if client_id:
            metrics = [m for m in metrics if m.client_id == client_id]
        
        if since:
            metrics = [m for m in metrics if m.start_time >= since]
        
        # Sort by start time (most recent first)
        metrics.sort(key=lambda m: m.start_time, reverse=True)
        
        if limit:
            metrics = metrics[:limit]
        
        return metrics
    
    def get_metric_summary(
        self,
        name: str,
        since: datetime = None
    ) -> Dict[str, Any]:
        """Get metric summary statistics.
        
        Args:
            name: Metric name
            since: Only include points after this timestamp
            
        Returns:
            Dictionary with summary statistics
        """
        points = self.get_metric_history(name, since=since)
        
        if not points:
            return {
                "name": name,
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "latest": None,
                "since": since.isoformat() if since else None
            }
        
        values = [p.value for p in points]
        
        return {
            "name": name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1],
            "latest_timestamp": points[-1].timestamp.isoformat(),
            "since": since.isoformat() if since else None
        }
    
    def get_queue_metrics(self) -> Dict[str, Any]:
        """Get current queue metrics from Redis.
        
        Returns:
            Dictionary with queue metrics
        """
        try:
            from ..workers.celery_app import task_monitor
            
            queue_info = task_monitor.get_queue_lengths()
            
            # Record queue metrics
            for queue_name, length in queue_info.get("queues", {}).items():
                self.record_metric(f"queue.length.{queue_name}", length)
            
            self.record_metric("queue.total_length", queue_info.get("total_queued", 0))
            
            return queue_info
            
        except Exception as e:
            logger.error("Failed to get queue metrics", error=str(e))
            return {"error": str(e)}
    
    def get_worker_metrics(self) -> Dict[str, Any]:
        """Get current worker metrics.
        
        Returns:
            Dictionary with worker metrics
        """
        try:
            from ..workers.celery_app import task_monitor
            
            worker_stats = task_monitor.get_worker_stats()
            active_tasks = task_monitor.get_active_tasks()
            
            # Record worker metrics
            self.record_metric("workers.total", worker_stats.get("total_workers", 0))
            self.record_metric("tasks.active", active_tasks.get("total_active", 0))
            
            return {
                "worker_stats": worker_stats,
                "active_tasks": active_tasks
            }
            
        except Exception as e:
            logger.error("Failed to get worker metrics", error=str(e))
            return {"error": str(e)}
    
    def cleanup_old_metrics(self, older_than: timedelta = timedelta(hours=24)):
        """Clean up old metrics to prevent memory growth.
        
        Args:
            older_than: Remove metrics older than this duration
        """
        cutoff_time = datetime.utcnow() - older_than
        
        with self._lock:
            # Clean up metric points
            for name, points in self._metrics.items():
                # Convert to list to avoid modifying deque during iteration
                points_list = list(points)
                points.clear()
                
                # Add back only recent points
                for point in points_list:
                    if point.timestamp >= cutoff_time:
                        points.append(point)
            
            # Clean up processing metrics
            self._processing_metrics = [
                m for m in self._processing_metrics
                if m.start_time >= cutoff_time
            ]
        
        logger.info(
            "Metrics cleanup completed",
            cutoff_time=cutoff_time.isoformat(),
            older_than_hours=older_than.total_seconds() / 3600
        )
    
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics report.
        
        Returns:
            Dictionary with all current metrics
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Get system metrics
        queue_metrics = self.get_queue_metrics()
        worker_metrics = self.get_worker_metrics()
        
        # Get processing summaries
        processing_summaries = {}
        operations = set(m.operation for m in self._processing_metrics)
        
        for operation in operations:
            recent_metrics = self.get_processing_metrics_history(
                operation=operation,
                since=one_hour_ago
            )
            
            if recent_metrics:
                durations = [m.duration_seconds for m in recent_metrics if m.end_time]
                throughputs = [m.throughput_per_second for m in recent_metrics if m.end_time]
                success_rates = [m.success_rate for m in recent_metrics if m.end_time]
                
                processing_summaries[operation] = {
                    "count": len(recent_metrics),
                    "avg_duration": sum(durations) / len(durations) if durations else 0,
                    "avg_throughput": sum(throughputs) / len(throughputs) if throughputs else 0,
                    "avg_success_rate": sum(success_rates) / len(success_rates) if success_rates else 0,
                    "total_items": sum(m.items_processed for m in recent_metrics),
                    "total_errors": sum(m.error_count for m in recent_metrics)
                }
        
        return {
            "timestamp": now.isoformat(),
            "queue_metrics": queue_metrics,
            "worker_metrics": worker_metrics,
            "processing_summaries": processing_summaries,
            "metric_counts": {name: len(points) for name, points in self._metrics.items()},
            "total_processing_metrics": len(self._processing_metrics)
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


class MetricsMiddleware:
    """Middleware for automatic metrics collection."""
    
    def __init__(self, collector: MetricsCollector = None):
        self.collector = collector or metrics_collector
    
    def track_request(self, request_path: str, method: str, client_id: str = None):
        """Track HTTP request metrics."""
        start_time = time.time()
        
        def finish_tracking(status_code: int):
            duration = time.time() - start_time
            
            self.collector.record_metric(
                "http.request.duration",
                duration,
                {
                    "path": request_path,
                    "method": method,
                    "status_code": str(status_code),
                    "client_id": client_id or "unknown"
                }
            )
            
            self.collector.record_metric(
                "http.request.count",
                1,
                {
                    "path": request_path,
                    "method": method,
                    "status_code": str(status_code),
                    "client_id": client_id or "unknown"
                }
            )
        
        return finish_tracking


# Global metrics middleware instance
metrics_middleware = MetricsMiddleware()