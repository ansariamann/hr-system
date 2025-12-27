"""Production monitoring and health check endpoints."""

from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse
import structlog

from ..core.health import health_checker
from ..core.observability import observability_system
from ..core.alerts import alert_manager
from ..core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health", summary="Comprehensive health check")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check for all critical services.
    
    Returns detailed health status for:
    - Database connectivity and performance
    - Redis connectivity and performance  
    - Celery worker availability and queue status
    - System resources (CPU, memory, disk)
    - File storage accessibility
    """
    try:
        health_report = await health_checker.run_all_checks()
        return health_report
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/simple", summary="Simple health check")
async def simple_health_check() -> Dict[str, str]:
    """
    Simple health check that returns basic status.
    Used by load balancers and monitoring systems.
    """
    try:
        health_report = await health_checker.run_all_checks()
        status = health_report["overall_status"]
        
        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Simple health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/readiness", summary="Readiness probe")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes-style readiness probe.
    Returns 200 if service is ready to accept traffic.
    """
    try:
        health_report = await health_checker.run_all_checks()
        
        # Service is ready if database and Redis are healthy
        db_healthy = any(
            check["name"] == "database" and check["status"] == "healthy"
            for check in health_report["checks"]
        )
        redis_healthy = any(
            check["name"] == "redis" and check["status"] == "healthy"
            for check in health_report["checks"]
        )
        
        if db_healthy and redis_healthy:
            return {
                "ready": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="Service not ready - database or Redis unavailable"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness probe failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"Readiness check failed: {str(e)}")


@router.get("/liveness", summary="Liveness probe")
async def liveness_probe() -> Dict[str, Any]:
    """
    Kubernetes-style liveness probe.
    Returns 200 if service is alive and should not be restarted.
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - settings.startup_time).total_seconds()
    }


@router.get("/metrics", response_class=PlainTextResponse, summary="Prometheus metrics")
async def prometheus_metrics() -> str:
    """
    Prometheus-compatible metrics endpoint.
    Returns metrics in Prometheus text format.
    """
    try:
        # Get comprehensive diagnostic data
        diagnostic_data = await observability_system.get_60_second_diagnostic()
        
        metrics_lines = []
        
        # System health metrics
        system_health = diagnostic_data.get("system_health", {})
        if "healthy_checks" in system_health:
            metrics_lines.append(f"ats_health_checks_healthy {system_health['healthy_checks']}")
            metrics_lines.append(f"ats_health_checks_total {system_health['total_checks']}")
            metrics_lines.append(f"ats_health_checks_unhealthy {system_health['unhealthy_checks']}")
        
        # Performance metrics
        performance_summary = diagnostic_data.get("performance_summary", {})
        for operation, perf in performance_summary.items():
            metrics_lines.append(f'ats_operation_p95_seconds{{operation="{operation}"}} {perf.get("p95_ms", 0) / 1000}')
            metrics_lines.append(f'ats_operation_error_rate{{operation="{operation}"}} {perf.get("error_rate", 0)}')
            metrics_lines.append(f'ats_operation_throughput_per_second{{operation="{operation}"}} {perf.get("throughput_per_second", 0)}')
        
        # Queue metrics
        queue_status = diagnostic_data.get("queue_status", {})
        if "total_queued" in queue_status:
            metrics_lines.append(f"ats_queue_depth_total {queue_status['total_queued']}")
        
        # Worker metrics
        worker_status = diagnostic_data.get("worker_status", {})
        if "total_workers" in worker_status:
            metrics_lines.append(f"ats_workers_total {worker_status['total_workers']}")
            metrics_lines.append(f"ats_workers_active_tasks {worker_status.get('active_tasks', 0)}")
        
        # Cost metrics
        cost_summary = diagnostic_data.get("cost_summary", {})
        if "current_hourly_cost" in cost_summary:
            metrics_lines.append(f"ats_estimated_cost_per_hour {cost_summary['current_hourly_cost']}")
            metrics_lines.append(f"ats_resource_efficiency {cost_summary.get('resource_efficiency', 0)}")
        
        # Alert metrics
        alert_count = diagnostic_data.get("alert_count", 0)
        metrics_lines.append(f"ats_active_alerts_total {alert_count}")
        
        # Collection time metric
        collection_time = diagnostic_data.get("collection_time_seconds", 0)
        metrics_lines.append(f"ats_diagnostic_collection_seconds {collection_time}")
        
        # Overall status metric (0=unhealthy, 1=degraded, 2=healthy)
        overall_status = diagnostic_data.get("overall_status", "unknown")
        status_value = {
            "healthy": 2,
            "degraded": 1,
            "unhealthy": 0,
            "unknown": 0
        }.get(overall_status, 0)
        metrics_lines.append(f"ats_overall_status {status_value}")
        
        return "\n".join(metrics_lines) + "\n"
        
    except Exception as e:
        logger.error("Failed to generate Prometheus metrics", error=str(e))
        return f"# Error generating metrics: {str(e)}\n"


@router.get("/diagnostic", summary="60-second diagnostic")
async def diagnostic_endpoint() -> Dict[str, Any]:
    """
    Comprehensive diagnostic information within 60 seconds.
    
    Provides detailed system status, performance metrics, queue status,
    worker health, recent errors, cost analysis, and trend information.
    """
    try:
        diagnostic_data = await observability_system.get_60_second_diagnostic()
        return diagnostic_data
    except Exception as e:
        logger.error("Diagnostic endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Diagnostic failed: {str(e)}")


@router.get("/alerts", summary="Active alerts")
async def get_active_alerts() -> Dict[str, Any]:
    """Get all currently active alerts."""
    try:
        # Check for new alerts
        new_alerts = await observability_system.check_alerts()
        
        # Get all active alerts
        active_alerts = list(observability_system._active_alerts.values())
        
        return {
            "active_alerts": [alert.to_dict() for alert in active_alerts],
            "alert_count": len(active_alerts),
            "new_alerts_detected": len(new_alerts),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.post("/alerts/{alert_name}/clear", summary="Clear alert")
async def clear_alert(alert_name: str) -> Dict[str, Any]:
    """Clear a specific active alert."""
    try:
        success = observability_system.clear_alert(alert_name)
        
        if success:
            return {
                "message": f"Alert '{alert_name}' cleared successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Alert '{alert_name}' not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clear alert", alert_name=alert_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear alert: {str(e)}")


@router.get("/trends", summary="Historical trends")
async def get_trends(hours: int = 24) -> Dict[str, Any]:
    """
    Get historical trend analysis.
    
    Args:
        hours: Number of hours to look back (default: 24)
    """
    try:
        if hours < 1 or hours > 168:  # Max 1 week
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")
        
        trends = observability_system.get_historical_trends(hours_back=hours)
        return trends
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get trends", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get trends: {str(e)}")


@router.get("/alert-rules", summary="Get alert rules")
async def get_alert_rules() -> Dict[str, Any]:
    """Get all configured alert rules."""
    try:
        rules = alert_manager.get_alert_rules()
        return {
            "alert_rules": [rule.to_dict() for rule in rules.values()],
            "total_rules": len(rules),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get alert rules", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert rules: {str(e)}")


@router.get("/notification-configs", summary="Get notification configurations")
async def get_notification_configs() -> Dict[str, Any]:
    """Get all notification channel configurations."""
    try:
        configs = alert_manager.get_notification_configs()
        return {
            "notification_configs": [config.to_dict() for config in configs.values()],
            "total_configs": len(configs),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get notification configs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get notification configs: {str(e)}")