"""API endpoints for comprehensive observability and metrics."""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from uuid import UUID
from datetime import datetime, timedelta
import structlog

from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.core.observability import observability_system, AlertSeverity
from ats_backend.core.alerts import alert_manager, AlertRule, NotificationChannel, NotificationConfig
from ats_backend.core.logging import performance_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/diagnostic")
async def get_60_second_diagnostic(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive diagnostic information within 60 seconds."""
    try:
        with performance_logger.log_operation_time(
            "60_second_diagnostic",
            user_id=str(current_user.id)
        ):
            diagnostic_data = await observability_system.get_60_second_diagnostic()
        
        logger.info(
            "60-second diagnostic completed",
            user_id=str(current_user.id),
            collection_time=diagnostic_data.get("collection_time_seconds", 0),
            overall_status=diagnostic_data.get("overall_status", "unknown"),
            alert_count=diagnostic_data.get("alert_count", 0)
        )
        
        return diagnostic_data
        
    except Exception as e:
        logger.error(
            "Failed to get 60-second diagnostic",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get diagnostic: {str(e)}"
        )


@router.get("/performance")
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
        
        logger.info(
            "Performance metrics retrieved",
            user_id=str(current_user.id),
            operation=operation,
            metrics_count=len(performance_metrics)
        )
        
        return {
            "metrics": {op: perf.to_dict() for op, perf in performance_metrics.items()},
            "timestamp": datetime.utcnow().isoformat(),
            "operation_filter": operation
        }
        
    except Exception as e:
        logger.error(
            "Failed to get performance metrics",
            user_id=str(current_user.id),
            operation=operation,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance metrics: {str(e)}"
        )


@router.get("/cost")
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
        
        logger.info(
            "Cost metrics retrieved",
            user_id=str(current_user.id),
            hourly_cost=cost_metrics.total_estimated_cost_per_hour,
            resource_efficiency=cost_metrics.resource_efficiency
        )
        
        return cost_metrics.to_dict()
        
    except Exception as e:
        logger.error(
            "Failed to get cost metrics",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cost metrics: {str(e)}"
        )


@router.get("/alerts")
async def get_active_alerts(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get active alerts."""
    try:
        active_alerts = await observability_system.check_alerts()
        
        logger.info(
            "Active alerts retrieved",
            user_id=str(current_user.id),
            alert_count=len(active_alerts)
        )
        
        return {
            "alerts": [alert.to_dict() for alert in active_alerts],
            "count": len(active_alerts),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to get active alerts",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active alerts: {str(e)}"
        )


@router.post("/alerts/check")
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
        
        # Process alerts through alert manager
        notification_results = []
        for alert in new_alerts:
            result = await alert_manager.process_alert(alert)
            notification_results.append(result)
        
        logger.info(
            "Alert check triggered",
            user_id=str(current_user.id),
            new_alerts=len(new_alerts),
            notifications_sent=sum(notification_results)
        )
        
        return {
            "new_alerts": len(new_alerts),
            "notifications_sent": sum(notification_results),
            "alerts": [alert.to_dict() for alert in new_alerts],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to trigger alert check",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger alert check: {str(e)}"
        )


@router.delete("/alerts/{alert_name}")
async def clear_alert(
    alert_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clear an active alert."""
    try:
        success = observability_system.clear_alert(alert_name)
        
        logger.info(
            "Alert clear attempted",
            user_id=str(current_user.id),
            alert_name=alert_name,
            success=success
        )
        
        return {
            "success": success,
            "alert_name": alert_name,
            "message": f"Alert {alert_name} {'cleared' if success else 'not found'}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to clear alert",
            user_id=str(current_user.id),
            alert_name=alert_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear alert: {str(e)}"
        )


@router.get("/trends")
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
        
        logger.info(
            "Historical trends retrieved",
            user_id=str(current_user.id),
            hours_back=hours_back,
            operations_tracked=trends["summary"]["operations_tracked"],
            total_alerts=trends["summary"]["total_alerts"]
        )
        
        return trends
        
    except Exception as e:
        logger.error(
            "Failed to get historical trends",
            user_id=str(current_user.id),
            hours_back=hours_back,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get historical trends: {str(e)}"
        )


@router.get("/alert-rules")
async def get_alert_rules(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all alert rules."""
    try:
        alert_rules = alert_manager.get_alert_rules()
        
        logger.info(
            "Alert rules retrieved",
            user_id=str(current_user.id),
            rules_count=len(alert_rules)
        )
        
        return {
            "rules": {name: rule.to_dict() for name, rule in alert_rules.items()},
            "count": len(alert_rules),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to get alert rules",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert rules: {str(e)}"
        )


@router.post("/alert-rules")
async def create_alert_rule(
    rule_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create or update an alert rule."""
    try:
        # Validate required fields
        required_fields = ["name", "condition", "threshold", "severity"]
        for field in required_fields:
            if field not in rule_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Create alert rule
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
        
        logger.info(
            "Alert rule created/updated",
            user_id=str(current_user.id),
            rule_name=rule.name,
            severity=rule.severity.value
        )
        
        return {
            "success": True,
            "rule": rule.to_dict(),
            "message": f"Alert rule '{rule.name}' created/updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        logger.error(
            "Invalid alert rule data",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid alert rule data: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Failed to create alert rule",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert rule: {str(e)}"
        )


@router.delete("/alert-rules/{rule_name}")
async def delete_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete an alert rule."""
    try:
        success = alert_manager.remove_alert_rule(rule_name)
        
        logger.info(
            "Alert rule deletion attempted",
            user_id=str(current_user.id),
            rule_name=rule_name,
            success=success
        )
        
        return {
            "success": success,
            "rule_name": rule_name,
            "message": f"Alert rule '{rule_name}' {'deleted' if success else 'not found'}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to delete alert rule",
            user_id=str(current_user.id),
            rule_name=rule_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete alert rule: {str(e)}"
        )


@router.put("/alert-rules/{rule_name}/enable")
async def enable_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Enable an alert rule."""
    try:
        success = alert_manager.enable_alert_rule(rule_name)
        
        logger.info(
            "Alert rule enable attempted",
            user_id=str(current_user.id),
            rule_name=rule_name,
            success=success
        )
        
        return {
            "success": success,
            "rule_name": rule_name,
            "message": f"Alert rule '{rule_name}' {'enabled' if success else 'not found'}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to enable alert rule",
            user_id=str(current_user.id),
            rule_name=rule_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable alert rule: {str(e)}"
        )


@router.put("/alert-rules/{rule_name}/disable")
async def disable_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Disable an alert rule."""
    try:
        success = alert_manager.disable_alert_rule(rule_name)
        
        logger.info(
            "Alert rule disable attempted",
            user_id=str(current_user.id),
            rule_name=rule_name,
            success=success
        )
        
        return {
            "success": success,
            "rule_name": rule_name,
            "message": f"Alert rule '{rule_name}' {'disabled' if success else 'not found'}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to disable alert rule",
            user_id=str(current_user.id),
            rule_name=rule_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable alert rule: {str(e)}"
        )


@router.get("/notification-configs")
async def get_notification_configs(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get notification configurations."""
    try:
        configs = alert_manager.get_notification_configs()
        
        logger.info(
            "Notification configs retrieved",
            user_id=str(current_user.id),
            configs_count=len(configs)
        )
        
        return {
            "configs": {channel.value: config.to_dict() for channel, config in configs.items()},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to get notification configs",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification configs: {str(e)}"
        )


@router.post("/notification-configs/{channel}/test")
async def test_notification_channel(
    channel: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test a notification channel."""
    try:
        # Validate channel
        try:
            notification_channel = NotificationChannel(channel)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notification channel: {channel}"
            )
        
        success = alert_manager.test_notification_channel(notification_channel)
        
        logger.info(
            "Notification channel test completed",
            user_id=str(current_user.id),
            channel=channel,
            success=success
        )
        
        return {
            "success": success,
            "channel": channel,
            "message": f"Notification channel '{channel}' test {'passed' if success else 'failed'}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to test notification channel",
            user_id=str(current_user.id),
            channel=channel,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test notification channel: {str(e)}"
        )


@router.put("/thresholds")
async def update_alert_thresholds(
    thresholds: Dict[str, float],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update alert thresholds."""
    try:
        observability_system.update_alert_thresholds(thresholds)
        
        logger.info(
            "Alert thresholds updated",
            user_id=str(current_user.id),
            thresholds=thresholds
        )
        
        return {
            "success": True,
            "updated_thresholds": thresholds,
            "message": "Alert thresholds updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Failed to update alert thresholds",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update alert thresholds: {str(e)}"
        )


@router.get("/dashboard")
async def get_observability_dashboard(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive observability dashboard data."""
    try:
        with performance_logger.log_operation_time(
            "get_observability_dashboard",
            user_id=str(current_user.id)
        ):
            # Get all dashboard data
            diagnostic_data = await observability_system.get_60_second_diagnostic()
            performance_metrics = await observability_system.collect_performance_metrics()
            cost_metrics = await observability_system.collect_cost_metrics()
            trends = observability_system.get_historical_trends(24)
            
            dashboard_data = {
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
        
        logger.info(
            "Observability dashboard data retrieved",
            user_id=str(current_user.id),
            overall_status=dashboard_data["overall_status"],
            alert_count=dashboard_data["alert_summary"]["total"],
            collection_time=dashboard_data["collection_time_seconds"]
        )
        
        return dashboard_data
        
    except Exception as e:
        logger.error(
            "Failed to get observability dashboard",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get observability dashboard: {str(e)}"
        )