"""Production monitoring, health check, and observability endpoints."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import PlainTextResponse
import structlog

from ..core.health import health_checker
from ..core.observability import observability_system, AlertSeverity
from ..core.alerts import alert_manager, AlertRule, NotificationChannel
from ..core.config import settings
from ..core.database import db_manager
from ..core.logging import performance_logger
from ..auth.dependencies import get_current_user
from ..auth.models import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/database/source", summary="Active database source details")
async def database_source() -> Dict[str, Any]:
    """Return active database source metadata used by the backend runtime."""
    try:
        from sqlalchemy.engine.url import make_url

        parsed = make_url(settings.database_url)
        return {
            "engine": parsed.drivername.split("+")[0],
            "host": parsed.host,
            "port": parsed.port,
            "database": parsed.database,
            "connected": db_manager.health_check(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error("Failed to read database source", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to read database source: {str(e)}")


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
        diagnostic_data = await observability_system.get_60_second_diagnostic()
        metrics_lines = []
        
        system_health = diagnostic_data.get("system_health", {})
        if "healthy_checks" in system_health:
            metrics_lines.append(f"ats_health_checks_healthy {system_health['healthy_checks']}")
            metrics_lines.append(f"ats_health_checks_total {system_health['total_checks']}")
            metrics_lines.append(f"ats_health_checks_unhealthy {system_health['unhealthy_checks']}")
        
        performance_summary = diagnostic_data.get("performance_summary", {})
        for operation, perf in performance_summary.items():
            metrics_lines.append(f'ats_operation_p95_seconds{{operation="{operation}"}} {perf.get("p95_ms", 0) / 1000}')
            metrics_lines.append(f'ats_operation_error_rate{{operation="{operation}"}} {perf.get("error_rate", 0)}')
            metrics_lines.append(f'ats_operation_throughput_per_second{{operation="{operation}"}} {perf.get("throughput_per_second", 0)}')
        
        queue_status = diagnostic_data.get("queue_status", {})
        if "total_queued" in queue_status:
            metrics_lines.append(f"ats_queue_depth_total {queue_status['total_queued']}")
        
        worker_status = diagnostic_data.get("worker_status", {})
        if "total_workers" in worker_status:
            metrics_lines.append(f"ats_workers_total {worker_status['total_workers']}")
            metrics_lines.append(f"ats_workers_active_tasks {worker_status.get('active_tasks', 0)}")
        
        cost_summary = diagnostic_data.get("cost_summary", {})
        if "current_hourly_cost" in cost_summary:
            metrics_lines.append(f"ats_estimated_cost_per_hour {cost_summary['current_hourly_cost']}")
            metrics_lines.append(f"ats_resource_efficiency {cost_summary.get('resource_efficiency', 0)}")
        
        alert_count = diagnostic_data.get("alert_count", 0)
        metrics_lines.append(f"ats_active_alerts_total {alert_count}")
        
        collection_time = diagnostic_data.get("collection_time_seconds", 0)
        metrics_lines.append(f"ats_diagnostic_collection_seconds {collection_time}")
        
        overall_status = diagnostic_data.get("overall_status", "unknown")
        status_value = {
            "healthy": 2,
            "degraded": 1,
            "unhealthy": 0,
            "unknown": 0
        }.get(overall_status, 0)
        metrics_lines.append(f"ats_overall_status {status_value}")
        
        return "\\n".join(metrics_lines) + "\\n"
        
    except Exception as e:
        logger.error("Failed to generate Prometheus metrics", error=str(e))
        return f"# Error generating metrics: {str(e)}\\n"


@router.get("/diagnostic", summary="60-second diagnostic")
async def diagnostic_endpoint(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Comprehensive diagnostic information within 60 seconds."""
    try:
        with performance_logger.log_operation_time(
            "60_second_diagnostic",
            user_id=str(current_user.id)
        ):
            diagnostic_data = await observability_system.get_60_second_diagnostic()
        return diagnostic_data
    except Exception as e:
        logger.error("Diagnostic endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Diagnostic failed: {str(e)}")


@router.get("/performance", summary="Performance metrics")
async def get_performance_metrics(
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive performance metrics."""
    try:
        with performance_logger.log_operation_time(
            "get_performance_metrics",
            user_id=str(current_user.id),
            operation=operation
        ):
            performance_metrics = await observability_system.collect_performance_metrics(operation)
        
        return {
            "metrics": {op: perf.to_dict() for op, perf in performance_metrics.items()},
            "timestamp": datetime.utcnow().isoformat(),
            "operation_filter": operation
        }
    except Exception as e:
        logger.error("Failed to get performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/cost", summary="Cost metrics")
async def get_cost_metrics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get cost and resource consumption metrics."""
    try:
        with performance_logger.log_operation_time(
            "get_cost_metrics",
            user_id=str(current_user.id)
        ):
            cost_metrics = await observability_system.collect_cost_metrics()
        
        return cost_metrics.to_dict()
    except Exception as e:
        logger.error("Failed to get cost metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get cost metrics: {str(e)}")


@router.get("/alerts", summary="Active alerts")
async def get_active_alerts(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all currently active alerts."""
    try:
        active_alerts = await observability_system.check_alerts()
        return {
            "alerts": [alert.to_dict() for alert in active_alerts],
            "count": len(active_alerts),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get active alerts: {str(e)}")


@router.post("/alerts/check", summary="Trigger alert check")
async def trigger_alert_check(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Trigger manual alert check."""
    try:
        with performance_logger.log_operation_time(
            "trigger_alert_check",
            user_id=str(current_user.id)
        ):
            new_alerts = await observability_system.check_alerts()
            
        notification_results = []
        for alert in new_alerts:
            result = await alert_manager.process_alert(alert)
            notification_results.append(result)
            
        return {
            "new_alerts": len(new_alerts),
            "notifications_sent": sum(notification_results),
            "alerts": [alert.to_dict() for alert in new_alerts],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to trigger alert check", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger alert check: {str(e)}")


@router.delete("/alerts/{alert_name}", summary="Clear an active alert")
async def clear_alert(
    alert_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clear an active alert."""
    try:
        success = observability_system.clear_alert(alert_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_name} not found")
        return {
            "success": success,
            "alert_name": alert_name,
            "message": f"Alert {alert_name} cleared",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clear alert", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear alert: {str(e)}")


@router.get("/trends", summary="Historical trends")
async def get_historical_trends(
    hours_back: int = Query(24, description="Hours to look back"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get historical trend analysis."""
    try:
        with performance_logger.log_operation_time(
            "get_historical_trends",
            user_id=str(current_user.id),
            hours_back=hours_back
        ):
            trends = observability_system.get_historical_trends(hours_back)
        return trends
    except Exception as e:
        logger.error("Failed to get trends", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get trends: {str(e)}")


@router.get("/alert-rules", summary="Get alert rules")
async def get_alert_rules(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all configured alert rules."""
    try:
        rules = alert_manager.get_alert_rules()
        return {
            "rules": {name: rule.to_dict() for name, rule in rules.items()},
            "count": len(rules),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get alert rules", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert rules: {str(e)}")


@router.post("/alert-rules", summary="Create or update an alert rule")
async def create_alert_rule(
    rule_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create or update an alert rule."""
    try:
        required_fields = ["name", "condition", "threshold", "severity"]
        for field in required_fields:
            if field not in rule_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
        rule = AlertRule(
            name=rule_data["name"],
            condition=rule_data["condition"],
            threshold=float(rule_data["threshold"]),
            severity=AlertSeverity(rule_data["severity"]),
            enabled=rule_data.get("enabled", True),
            cooldown_minutes=rule_data.get("cooldown_minutes", 15),
            notification_channels=[
                NotificationChannel(ch) for ch in rule_data.get("notification_channels", ["log"])
            ]
        )
        
        alert_manager.add_alert_rule(rule)
        
        return {
            "success": True,
            "rule": rule.to_dict(),
            "message": f"Alert rule '{rule.name}' created/updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to create alert rule", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create alert rule: {str(e)}")


@router.delete("/alert-rules/{rule_name}", summary="Delete an alert rule")
async def delete_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete an alert rule."""
    try:
        success = alert_manager.remove_alert_rule(rule_name)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {
            "success": success,
            "rule_name": rule_name,
            "message": f"Alert rule '{rule_name}' deleted",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete alert rule", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete alert rule: {str(e)}")


@router.put("/alert-rules/{rule_name}/enable", summary="Enable an alert rule")
async def enable_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Enable an alert rule."""
    try:
        success = alert_manager.enable_alert_rule(rule_name)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {
            "success": success,
            "rule_name": rule_name,
            "message": f"Alert rule '{rule_name}' enabled",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to enable alert rule", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to enable alert rule: {str(e)}")


@router.put("/alert-rules/{rule_name}/disable", summary="Disable an alert rule")
async def disable_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Disable an alert rule."""
    try:
        success = alert_manager.disable_alert_rule(rule_name)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {
            "success": success,
            "rule_name": rule_name,
            "message": f"Alert rule '{rule_name}' disabled",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to disable alert rule", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to disable alert rule: {str(e)}")


@router.get("/notification-configs", summary="Get notification configurations")
async def get_notification_configs(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all notification channel configurations."""
    try:
        configs = alert_manager.get_notification_configs()
        return {
            "configs": {channel.value: config.to_dict() for channel, config in configs.items()},
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get notification configs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get notification configs: {str(e)}")


@router.post("/notification-configs/{channel}/test", summary="Test a notification channel")
async def test_notification_channel(
    channel: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test a notification channel."""
    try:
        notification_channel = NotificationChannel(channel)
        success = alert_manager.test_notification_channel(notification_channel)
        return {
            "success": success,
            "channel": channel,
            "message": f"Notification channel '{channel}' test {'passed' if success else 'failed'}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid notification channel: {channel}")
    except Exception as e:
        logger.error("Failed to test notification channel", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to test notification channel: {str(e)}")


@router.put("/thresholds", summary="Update alert thresholds")
async def update_alert_thresholds(
    thresholds: Dict[str, float],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update alert thresholds."""
    try:
        observability_system.update_alert_thresholds(thresholds)
        return {
            "success": True,
            "updated_thresholds": thresholds,
            "message": "Alert thresholds updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to update alert thresholds", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update alert thresholds: {str(e)}")


@router.get("/dashboard", summary="Comprehensive observability dashboard data")
async def get_observability_dashboard(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive observability dashboard data."""
    try:
        with performance_logger.log_operation_time(
            "get_observability_dashboard",
            user_id=str(current_user.id)
        ):
            diagnostic_data = await observability_system.get_60_second_diagnostic()
            performance_metrics = await observability_system.collect_performance_metrics()
            cost_metrics = await observability_system.collect_cost_metrics()
            trends = observability_system.get_historical_trends(24)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": diagnostic_data.get("overall_status", "unknown"),
                "system_health": diagnostic_data.get("system_health", {}),
                "performance_summary": {
                    op: {
                        "p95_ms": perf.p95_ms,
                        "error_rate": perf.error_rate,
                        "throughput_per_second": perf.throughput_per_second
                    }
                    for op, perf in performance_metrics.items()
                },
                "cost_summary": {
                    "hourly_cost": cost_metrics.total_estimated_cost_per_hour,
                    "daily_projection": cost_metrics.total_estimated_cost_per_hour * 24,
                    "monthly_projection": cost_metrics.total_estimated_cost_per_hour * 24 * 30,
                    "resource_efficiency": cost_metrics.resource_efficiency
                },
                "queue_status": diagnostic_data.get("queue_status", {}),
                "worker_status": diagnostic_data.get("worker_status", {}),
                "active_alerts": diagnostic_data.get("active_alerts", []),
                "alert_summary": {
                    "total": diagnostic_data.get("alert_count", 0),
                    "critical": len([a for a in diagnostic_data.get("active_alerts", []) if a.get("severity") == "critical"]),
                    "warning": len([a for a in diagnostic_data.get("active_alerts", []) if a.get("severity") == "warning"])
                },
                "trends": diagnostic_data.get("trend_analysis", {}),
                "collection_time_seconds": diagnostic_data.get("collection_time_seconds", 0)
            }
    except Exception as e:
        logger.error("Failed to get observability dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get observability dashboard: {str(e)}")
