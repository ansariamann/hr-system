"""Comprehensive observability and metrics system for production hardening."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import time
import threading
import asyncio
import statistics
import structlog
import psutil
from pathlib import Path

from .config import settings
from .metrics import metrics_collector, MetricPoint, ProcessingMetrics
from .health import health_checker, HealthStatus
from .redis import get_redis_client

logger = structlog.get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """Types of metrics we collect."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Alert:
    """Alert definition and state."""
    name: str
    condition: str
    severity: AlertSeverity
    threshold: float
    current_value: float
    triggered_at: datetime
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "name": self.name,
            "condition": self.condition,
            "severity": self.severity.value,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "triggered_at": self.triggered_at.isoformat(),
            "message": self.message,
            "details": self.details
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for specific operations."""
    operation: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    count: int
    error_rate: float
    throughput_per_second: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert performance metrics to dictionary."""
        return {
            "operation": self.operation,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "avg_ms": self.avg_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "count": self.count,
            "error_rate": self.error_rate,
            "throughput_per_second": self.throughput_per_second,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CostMetrics:
    """Cost and resource consumption metrics."""
    cpu_cost_per_hour: float
    memory_cost_per_hour: float
    storage_cost_per_gb: float
    network_cost_per_gb: float
    total_estimated_cost_per_hour: float
    resource_efficiency: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cost metrics to dictionary."""
        return {
            "cpu_cost_per_hour": self.cpu_cost_per_hour,
            "memory_cost_per_hour": self.memory_cost_per_hour,
            "storage_cost_per_gb": self.storage_cost_per_gb,
            "network_cost_per_gb": self.network_cost_per_gb,
            "total_estimated_cost_per_hour": self.total_estimated_cost_per_hour,
            "resource_efficiency": self.resource_efficiency,
            "timestamp": self.timestamp.isoformat()
        }


class ObservabilitySystem:
    """Comprehensive observability and metrics system."""
    
    def __init__(self):
        self.logger = structlog.get_logger("observability")
        self._lock = threading.RLock()
        
        # Performance metrics storage
        self._performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._cost_history: deque = deque(maxlen=1000)
        
        # Alert system
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=1000)
        
        # Diagnostic cache for 60-second capability
        self._diagnostic_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=30)  # Cache for 30 seconds
        
        # Alert thresholds (configurable)
        self.alert_thresholds = {
            "resume_parse_time_p95": 5000.0,  # 5 seconds
            "ocr_fallback_rate": 0.3,  # 30%
            "duplicate_detection_hit_rate": 0.8,  # 80%
            "queue_depth_total": 100,  # 100 tasks
            "failed_ingestion_rate": 0.1,  # 10%
            "cpu_usage": 90.0,  # 90%
            "memory_usage": 90.0,  # 90%
            "disk_usage": 95.0,  # 95%
            "worker_count": 1,  # At least 1 worker
            "response_time_p95": 2000.0,  # 2 seconds
            "error_rate": 0.05,  # 5%
            "cost_per_hour": 10.0,  # $10/hour
        }
    
    async def collect_performance_metrics(self, operation: str = None) -> Dict[str, PerformanceMetrics]:
        """Collect comprehensive performance metrics."""
        try:
            performance_metrics = {}
            
            # Get operations to analyze
            operations = [operation] if operation else [
                "resume_parsing", "email_processing", "ocr_processing",
                "duplicate_detection", "api_requests", "database_queries"
            ]
            
            for op in operations:
                # Get processing metrics from collector
                processing_history = metrics_collector.get_processing_metrics_history(
                    operation=op,
                    since=datetime.utcnow() - timedelta(hours=1),
                    limit=1000
                )
                
                if processing_history:
                    # Calculate performance statistics
                    durations = [m.duration_seconds * 1000 for m in processing_history if m.end_time]
                    error_counts = [m.error_count for m in processing_history]
                    success_counts = [m.success_count for m in processing_history]
                    
                    if durations:
                        # Calculate percentiles
                        durations.sort()
                        p50 = statistics.median(durations)
                        p95 = durations[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0]
                        p99 = durations[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0]
                        
                        # Calculate error rate
                        total_errors = sum(error_counts)
                        total_success = sum(success_counts)
                        total_operations = total_errors + total_success
                        error_rate = total_errors / total_operations if total_operations > 0 else 0
                        
                        # Calculate throughput
                        time_span = (processing_history[0].start_time - processing_history[-1].start_time).total_seconds()
                        throughput = len(processing_history) / time_span if time_span > 0 else 0
                        
                        performance_metrics[op] = PerformanceMetrics(
                            operation=op,
                            p50_ms=p50,
                            p95_ms=p95,
                            p99_ms=p99,
                            avg_ms=statistics.mean(durations),
                            min_ms=min(durations),
                            max_ms=max(durations),
                            count=len(durations),
                            error_rate=error_rate,
                            throughput_per_second=throughput
                        )
                        
                        # Store in history
                        with self._lock:
                            self._performance_history[op].append(performance_metrics[op])
            
            return performance_metrics
            
        except Exception as e:
            self.logger.error("Failed to collect performance metrics", error=str(e))
            return {}
    
    async def collect_cost_metrics(self) -> CostMetrics:
        """Collect cost and resource consumption metrics."""
        try:
            # Get system resource usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Estimate costs (these would be configured based on actual cloud costs)
            cpu_cores = psutil.cpu_count()
            memory_gb = memory.total / (1024**3)
            disk_gb = disk.total / (1024**3)
            
            # Example cost calculations (would be environment-specific)
            cpu_cost_per_core_hour = 0.05  # $0.05 per core per hour
            memory_cost_per_gb_hour = 0.01  # $0.01 per GB per hour
            storage_cost_per_gb_month = 0.10  # $0.10 per GB per month
            
            cpu_cost = (cpu_percent / 100) * cpu_cores * cpu_cost_per_core_hour
            memory_cost = (memory.percent / 100) * memory_gb * memory_cost_per_gb_hour
            storage_cost = disk_gb * storage_cost_per_gb_month / (24 * 30)  # Convert to hourly
            
            # Calculate resource efficiency (lower is better)
            resource_efficiency = (cpu_percent + memory.percent) / 200  # 0-1 scale
            
            cost_metrics = CostMetrics(
                cpu_cost_per_hour=cpu_cost,
                memory_cost_per_hour=memory_cost,
                storage_cost_per_gb=storage_cost,
                network_cost_per_gb=0.0,  # Would need network monitoring
                total_estimated_cost_per_hour=cpu_cost + memory_cost + storage_cost,
                resource_efficiency=resource_efficiency
            )
            
            # Store in history
            with self._lock:
                self._cost_history.append(cost_metrics)
            
            return cost_metrics
            
        except Exception as e:
            self.logger.error("Failed to collect cost metrics", error=str(e))
            return CostMetrics(0, 0, 0, 0, 0, 0)
    
    async def check_alerts(self) -> List[Alert]:
        """Check all alert conditions and return active alerts."""
        try:
            new_alerts = []
            
            # Get current metrics
            performance_metrics = await self.collect_performance_metrics()
            cost_metrics = await self.collect_cost_metrics()
            
            # Get system metrics
            system_metrics = await self._get_system_metrics()
            queue_metrics = await self._get_queue_metrics()
            
            # Check performance alerts
            for operation, perf in performance_metrics.items():
                # Check P95 response time
                if perf.p95_ms > self.alert_thresholds.get(f"{operation}_p95", self.alert_thresholds["response_time_p95"]):
                    alert = Alert(
                        name=f"{operation}_high_p95",
                        condition=f"P95 response time > {self.alert_thresholds['response_time_p95']}ms",
                        severity=AlertSeverity.WARNING,
                        threshold=self.alert_thresholds["response_time_p95"],
                        current_value=perf.p95_ms,
                        triggered_at=datetime.utcnow(),
                        message=f"{operation} P95 response time is {perf.p95_ms:.1f}ms",
                        details=perf.to_dict()
                    )
                    new_alerts.append(alert)
                
                # Check error rate
                if perf.error_rate > self.alert_thresholds["error_rate"]:
                    alert = Alert(
                        name=f"{operation}_high_error_rate",
                        condition=f"Error rate > {self.alert_thresholds['error_rate']*100}%",
                        severity=AlertSeverity.CRITICAL,
                        threshold=self.alert_thresholds["error_rate"],
                        current_value=perf.error_rate,
                        triggered_at=datetime.utcnow(),
                        message=f"{operation} error rate is {perf.error_rate*100:.1f}%",
                        details=perf.to_dict()
                    )
                    new_alerts.append(alert)
            
            # Check system resource alerts
            if system_metrics.get("cpu_percent", 0) > self.alert_thresholds["cpu_usage"]:
                alert = Alert(
                    name="high_cpu_usage",
                    condition=f"CPU usage > {self.alert_thresholds['cpu_usage']}%",
                    severity=AlertSeverity.WARNING,
                    threshold=self.alert_thresholds["cpu_usage"],
                    current_value=system_metrics["cpu_percent"],
                    triggered_at=datetime.utcnow(),
                    message=f"CPU usage is {system_metrics['cpu_percent']:.1f}%",
                    details=system_metrics
                )
                new_alerts.append(alert)
            
            if system_metrics.get("memory_percent", 0) > self.alert_thresholds["memory_usage"]:
                alert = Alert(
                    name="high_memory_usage",
                    condition=f"Memory usage > {self.alert_thresholds['memory_usage']}%",
                    severity=AlertSeverity.WARNING,
                    threshold=self.alert_thresholds["memory_usage"],
                    current_value=system_metrics["memory_percent"],
                    triggered_at=datetime.utcnow(),
                    message=f"Memory usage is {system_metrics['memory_percent']:.1f}%",
                    details=system_metrics
                )
                new_alerts.append(alert)
            
            # Check queue depth alerts
            total_queued = queue_metrics.get("total_queued", 0)
            if total_queued > self.alert_thresholds["queue_depth_total"]:
                severity = AlertSeverity.CRITICAL if total_queued > 500 else AlertSeverity.WARNING
                alert = Alert(
                    name="high_queue_depth",
                    condition=f"Total queue depth > {self.alert_thresholds['queue_depth_total']}",
                    severity=severity,
                    threshold=self.alert_thresholds["queue_depth_total"],
                    current_value=total_queued,
                    triggered_at=datetime.utcnow(),
                    message=f"Total queue depth is {total_queued}",
                    details=queue_metrics
                )
                new_alerts.append(alert)
            
            # Check cost alerts
            if cost_metrics.total_estimated_cost_per_hour > self.alert_thresholds["cost_per_hour"]:
                alert = Alert(
                    name="high_cost",
                    condition=f"Estimated cost > ${self.alert_thresholds['cost_per_hour']}/hour",
                    severity=AlertSeverity.WARNING,
                    threshold=self.alert_thresholds["cost_per_hour"],
                    current_value=cost_metrics.total_estimated_cost_per_hour,
                    triggered_at=datetime.utcnow(),
                    message=f"Estimated cost is ${cost_metrics.total_estimated_cost_per_hour:.2f}/hour",
                    details=cost_metrics.to_dict()
                )
                new_alerts.append(alert)
            
            # Update active alerts
            with self._lock:
                for alert in new_alerts:
                    self._active_alerts[alert.name] = alert
                    self._alert_history.append(alert)
            
            return new_alerts
            
        except Exception as e:
            self.logger.error("Failed to check alerts", error=str(e))
            return []
    
    async def get_60_second_diagnostic(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information within 60 seconds."""
        try:
            # Check cache first
            now = datetime.utcnow()
            if (self._cache_timestamp and 
                now - self._cache_timestamp < self._cache_ttl and 
                self._diagnostic_cache):
                self.logger.info("Returning cached diagnostic data")
                return self._diagnostic_cache
            
            start_time = time.time()
            
            # Collect all diagnostic data concurrently
            tasks = [
                self._get_system_health(),
                self._get_performance_summary(),
                self._get_queue_status(),
                self._get_worker_status(),
                self._get_recent_errors(),
                self._get_cost_summary(),
                self._get_trend_analysis()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            system_health = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
            performance_summary = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
            queue_status = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}
            worker_status = results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])}
            recent_errors = results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])}
            cost_summary = results[5] if not isinstance(results[5], Exception) else {"error": str(results[5])}
            trend_analysis = results[6] if not isinstance(results[6], Exception) else {"error": str(results[6])}
            
            # Check for active alerts
            active_alerts = list(self._active_alerts.values())
            
            diagnostic_data = {
                "timestamp": now.isoformat(),
                "collection_time_seconds": time.time() - start_time,
                "system_health": system_health,
                "performance_summary": performance_summary,
                "queue_status": queue_status,
                "worker_status": worker_status,
                "recent_errors": recent_errors,
                "cost_summary": cost_summary,
                "trend_analysis": trend_analysis,
                "active_alerts": [alert.to_dict() for alert in active_alerts],
                "alert_count": len(active_alerts),
                "overall_status": self._determine_overall_status(system_health, active_alerts)
            }
            
            # Cache the results
            with self._lock:
                self._diagnostic_cache = diagnostic_data
                self._cache_timestamp = now
            
            self.logger.info(
                "60-second diagnostic completed",
                collection_time=diagnostic_data["collection_time_seconds"],
                alert_count=len(active_alerts),
                overall_status=diagnostic_data["overall_status"]
            )
            
            return diagnostic_data
            
        except Exception as e:
            self.logger.error("Failed to get 60-second diagnostic", error=str(e))
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": f"Failed to get diagnostic: {str(e)}",
                "overall_status": "error"
            }
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health information."""
        health_report = await health_checker.run_all_checks()
        return {
            "overall_status": health_report["overall_status"],
            "healthy_checks": health_report["summary"]["healthy_checks"],
            "total_checks": health_report["summary"]["total_checks"],
            "unhealthy_checks": health_report["summary"]["unhealthy_checks"],
            "check_time_ms": health_report["total_check_time_ms"]
        }
    
    async def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        performance_metrics = await self.collect_performance_metrics()
        
        summary = {}
        for operation, perf in performance_metrics.items():
            summary[operation] = {
                "p95_ms": perf.p95_ms,
                "error_rate": perf.error_rate,
                "throughput_per_second": perf.throughput_per_second,
                "count": perf.count
            }
        
        return summary
    
    async def _get_queue_status(self) -> Dict[str, Any]:
        """Get queue status."""
        return await self._get_queue_metrics()
    
    async def _get_worker_status(self) -> Dict[str, Any]:
        """Get worker status."""
        from ..workers.celery_app import task_monitor
        
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        
        return {
            "total_workers": worker_stats.get("total_workers", 0),
            "active_tasks": active_tasks.get("total_active", 0),
            "worker_health": worker_stats.get("worker_health", {}),
            "has_errors": "error" in worker_stats or "error" in active_tasks
        }
    
    async def _get_recent_errors(self) -> Dict[str, Any]:
        """Get recent error information."""
        # This would integrate with your error logging system
        # For now, return placeholder data
        return {
            "error_count_last_hour": 0,
            "critical_errors": 0,
            "most_common_error": None,
            "error_trend": "stable"
        }
    
    async def _get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary."""
        cost_metrics = await self.collect_cost_metrics()
        
        # Calculate daily/monthly projections
        daily_cost = cost_metrics.total_estimated_cost_per_hour * 24
        monthly_cost = daily_cost * 30
        
        return {
            "current_hourly_cost": cost_metrics.total_estimated_cost_per_hour,
            "projected_daily_cost": daily_cost,
            "projected_monthly_cost": monthly_cost,
            "resource_efficiency": cost_metrics.resource_efficiency,
            "cost_breakdown": {
                "cpu": cost_metrics.cpu_cost_per_hour,
                "memory": cost_metrics.memory_cost_per_hour,
                "storage": cost_metrics.storage_cost_per_gb
            }
        }
    
    async def _get_trend_analysis(self) -> Dict[str, Any]:
        """Get trend analysis."""
        with self._lock:
            # Analyze performance trends
            performance_trends = {}
            for operation, history in self._performance_history.items():
                if len(history) >= 2:
                    recent = list(history)[-10:]  # Last 10 measurements
                    older = list(history)[-20:-10] if len(history) >= 20 else []
                    
                    if older:
                        recent_avg = statistics.mean([p.p95_ms for p in recent])
                        older_avg = statistics.mean([p.p95_ms for p in older])
                        trend = "improving" if recent_avg < older_avg else "degrading"
                        change_percent = ((recent_avg - older_avg) / older_avg) * 100
                    else:
                        trend = "insufficient_data"
                        change_percent = 0
                    
                    performance_trends[operation] = {
                        "trend": trend,
                        "change_percent": change_percent
                    }
            
            # Analyze cost trends
            cost_trend = "stable"
            cost_change_percent = 0
            if len(self._cost_history) >= 10:
                recent_costs = [c.total_estimated_cost_per_hour for c in list(self._cost_history)[-5:]]
                older_costs = [c.total_estimated_cost_per_hour for c in list(self._cost_history)[-10:-5]]
                
                if older_costs:
                    recent_avg = statistics.mean(recent_costs)
                    older_avg = statistics.mean(older_costs)
                    cost_change_percent = ((recent_avg - older_avg) / older_avg) * 100
                    
                    if cost_change_percent > 10:
                        cost_trend = "increasing"
                    elif cost_change_percent < -10:
                        cost_trend = "decreasing"
        
        return {
            "performance_trends": performance_trends,
            "cost_trend": cost_trend,
            "cost_change_percent": cost_change_percent
        }
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": (disk.used / disk.total) * 100,
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        }
    
    async def _get_queue_metrics(self) -> Dict[str, Any]:
        """Get current queue metrics."""
        from ..workers.celery_app import task_monitor
        return task_monitor.get_queue_lengths()
    
    def _determine_overall_status(self, system_health: Dict[str, Any], active_alerts: List[Alert]) -> str:
        """Determine overall system status."""
        # Check for critical alerts
        critical_alerts = [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            return "critical"
        
        # Check system health
        if system_health.get("overall_status") == "unhealthy":
            return "unhealthy"
        
        # Check for warning alerts
        warning_alerts = [a for a in active_alerts if a.severity == AlertSeverity.WARNING]
        if warning_alerts:
            return "degraded"
        
        if system_health.get("overall_status") == "degraded":
            return "degraded"
        
        return "healthy"
    
    def get_historical_trends(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get historical trend analysis."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        with self._lock:
            # Filter historical data
            historical_performance = {}
            for operation, history in self._performance_history.items():
                filtered_history = [p for p in history if p.timestamp >= cutoff_time]
                if filtered_history:
                    historical_performance[operation] = [p.to_dict() for p in filtered_history]
            
            historical_costs = [c.to_dict() for c in self._cost_history if c.timestamp >= cutoff_time]
            historical_alerts = [a.to_dict() for a in self._alert_history if a.triggered_at >= cutoff_time]
        
        return {
            "time_range_hours": hours_back,
            "performance_history": historical_performance,
            "cost_history": historical_costs,
            "alert_history": historical_alerts,
            "summary": {
                "total_alerts": len(historical_alerts),
                "critical_alerts": len([a for a in historical_alerts if a["severity"] == "critical"]),
                "operations_tracked": len(historical_performance)
            }
        }
    
    def clear_alert(self, alert_name: str) -> bool:
        """Clear an active alert."""
        with self._lock:
            if alert_name in self._active_alerts:
                del self._active_alerts[alert_name]
                self.logger.info("Alert cleared", alert_name=alert_name)
                return True
            return False
    
    def update_alert_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update alert thresholds."""
        with self._lock:
            self.alert_thresholds.update(thresholds)
            self.logger.info("Alert thresholds updated", thresholds=thresholds)


# Global observability system instance
observability_system = ObservabilitySystem()