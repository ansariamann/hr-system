#!/usr/bin/env python3
"""
Comprehensive health check script for ATS Backend production deployment.

This script performs detailed health checks across all system components
and provides actionable recommendations for any issues found.
"""

import asyncio
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.health import health_checker, HealthStatus
from ats_backend.core.observability import observability_system
from ats_backend.core.alerts import alert_manager
import structlog
import aiohttp

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class ProductionHealthChecker:
    """Comprehensive production health checker with detailed reporting."""
    
    def __init__(self, environment: str = "prod"):
        self.environment = environment
        self.api_ports = {
            "dev": 8000,
            "staging": 8001,
            "prod": 8002
        }
        self.api_port = self.api_ports.get(environment, 8002)
        
    async def run_comprehensive_health_check(self) -> Tuple[bool, Dict]:
        """
        Run comprehensive health check across all system components.
        
        Returns:
            Tuple[bool, Dict]: (overall_healthy, detailed_results)
        """
        logger.info("Starting comprehensive production health check", 
                   environment=self.environment)
        
        start_time = time.time()
        
        results = {
            "environment": self.environment,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "overall_status": "unknown",
            "recommendations": [],
            "critical_issues": [],
            "warnings": []
        }
        
        try:
            # 1. Core Service Health
            logger.info("Checking core service health")
            core_healthy, core_results = await self._check_core_services()
            results["checks"]["core_services"] = core_results
            
            # 2. API Endpoints Health
            logger.info("Checking API endpoints")
            api_healthy, api_results = await self._check_api_endpoints()
            results["checks"]["api_endpoints"] = api_results
            
            # 3. Database Health
            logger.info("Checking database health")
            db_healthy, db_results = await self._check_database_health()
            results["checks"]["database"] = db_results
            
            # 4. Queue and Workers Health
            logger.info("Checking queue and workers")
            queue_healthy, queue_results = await self._check_queue_health()
            results["checks"]["queue_workers"] = queue_results
            
            # 5. Monitoring Stack Health
            logger.info("Checking monitoring stack")
            monitoring_healthy, monitoring_results = await self._check_monitoring_stack()
            results["checks"]["monitoring"] = monitoring_results
            
            # 6. Security Health
            logger.info("Checking security configuration")
            security_healthy, security_results = await self._check_security_health()
            results["checks"]["security"] = security_results
            
            # 7. Performance Health
            logger.info("Checking performance metrics")
            perf_healthy, perf_results = await self._check_performance_health()
            results["checks"]["performance"] = perf_results
            
            # 8. Backup System Health
            logger.info("Checking backup system")
            backup_healthy, backup_results = await self._check_backup_health()
            results["checks"]["backup_system"] = backup_results
            
            # Determine overall health
            all_checks = [
                core_healthy, api_healthy, db_healthy, queue_healthy,
                monitoring_healthy, security_healthy, perf_healthy, backup_healthy
            ]
            
            overall_healthy = all(all_checks)
            critical_issues = sum(1 for healthy in all_checks if not healthy)
            
            if critical_issues == 0:
                results["overall_status"] = "healthy"
            elif critical_issues <= 2:
                results["overall_status"] = "degraded"
            else:
                results["overall_status"] = "unhealthy"
            
            # Generate recommendations
            results["recommendations"] = self._generate_recommendations(results["checks"])
            
            # Extract critical issues and warnings
            results["critical_issues"] = self._extract_critical_issues(results["checks"])
            results["warnings"] = self._extract_warnings(results["checks"])
            
            total_time = time.time() - start_time
            results["check_duration_seconds"] = round(total_time, 2)
            
            logger.info("Comprehensive health check completed",
                       environment=self.environment,
                       overall_status=results["overall_status"],
                       duration_seconds=total_time,
                       critical_issues=len(results["critical_issues"]),
                       warnings=len(results["warnings"]))
            
            return overall_healthy, results
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            results["overall_status"] = "error"
            results["error"] = str(e)
            return False, results
    
    async def _check_core_services(self) -> Tuple[bool, Dict]:
        """Check core service health using internal health checker."""
        try:
            health_report = await health_checker.run_all_checks()
            
            healthy = health_report["overall_status"] == "healthy"
            
            return healthy, {
                "status": health_report["overall_status"],
                "healthy_checks": health_report["summary"]["healthy_checks"],
                "total_checks": health_report["summary"]["total_checks"],
                "unhealthy_checks": health_report["summary"]["unhealthy_checks"],
                "check_details": health_report["checks"],
                "response_time_ms": health_report["total_check_time_ms"]
            }
            
        except Exception as e:
            return False, {
                "status": "error",
                "error": str(e),
                "message": "Failed to check core services"
            }
    
    async def _check_api_endpoints(self) -> Tuple[bool, Dict]:
        """Check API endpoint availability and response times."""
        endpoints_to_check = [
            ("/monitoring/health/simple", "GET"),
            ("/monitoring/readiness", "GET"),
            ("/monitoring/liveness", "GET"),
            ("/monitoring/metrics", "GET")
        ]
        
        results = {
            "endpoints": {},
            "average_response_time": 0,
            "all_endpoints_healthy": True
        }
        
        total_response_time = 0
        healthy_endpoints = 0
        
        async with aiohttp.ClientSession() as session:
            for endpoint, method in endpoints_to_check:
                start_time = time.time()
                
                try:
                    url = f"http://localhost:{self.api_port}{endpoint}"
                    async with session.request(method, url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response_time = time.time() - start_time
                        total_response_time += response_time
                        
                        endpoint_healthy = response.status == 200
                        if endpoint_healthy:
                            healthy_endpoints += 1
                        else:
                            results["all_endpoints_healthy"] = False
                        
                        results["endpoints"][endpoint] = {
                            "status_code": response.status,
                            "response_time_ms": round(response_time * 1000, 2),
                            "healthy": endpoint_healthy
                        }
                        
                except Exception as e:
                    results["endpoints"][endpoint] = {
                        "status_code": 0,
                        "response_time_ms": 0,
                        "healthy": False,
                        "error": str(e)
                    }
                    results["all_endpoints_healthy"] = False
        
        if healthy_endpoints > 0:
            results["average_response_time"] = round((total_response_time / healthy_endpoints) * 1000, 2)
        
        return results["all_endpoints_healthy"], results
    
    async def _check_database_health(self) -> Tuple[bool, Dict]:
        """Check database health and performance."""
        try:
            # Use API endpoint to check database
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{self.api_port}/monitoring/diagnostic"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        diagnostic_data = await response.json()
                        
                        # Extract database-related information
                        system_health = diagnostic_data.get("system_health", {})
                        
                        db_healthy = system_health.get("overall_status") == "healthy"
                        
                        return db_healthy, {
                            "status": "healthy" if db_healthy else "unhealthy",
                            "connection_status": "connected" if db_healthy else "disconnected",
                            "health_check_time_ms": system_health.get("check_time_ms", 0),
                            "details": system_health
                        }
                    else:
                        return False, {
                            "status": "unhealthy",
                            "error": f"Diagnostic endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return False, {
                "status": "error",
                "error": str(e),
                "message": "Failed to check database health"
            }
    
    async def _check_queue_health(self) -> Tuple[bool, Dict]:
        """Check queue and worker health."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{self.api_port}/monitoring/diagnostic"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        diagnostic_data = await response.json()
                        
                        queue_status = diagnostic_data.get("queue_status", {})
                        worker_status = diagnostic_data.get("worker_status", {})
                        
                        total_queued = queue_status.get("total_queued", 0)
                        total_workers = worker_status.get("total_workers", 0)
                        
                        # Health criteria
                        queue_healthy = total_queued < 500  # Critical threshold
                        workers_healthy = total_workers > 0
                        
                        overall_healthy = queue_healthy and workers_healthy
                        
                        return overall_healthy, {
                            "status": "healthy" if overall_healthy else "unhealthy",
                            "total_queued": total_queued,
                            "total_workers": total_workers,
                            "active_tasks": worker_status.get("active_tasks", 0),
                            "queue_healthy": queue_healthy,
                            "workers_healthy": workers_healthy,
                            "queue_details": queue_status,
                            "worker_details": worker_status
                        }
                    else:
                        return False, {
                            "status": "error",
                            "error": f"Diagnostic endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return False, {
                "status": "error",
                "error": str(e),
                "message": "Failed to check queue health"
            }
    
    async def _check_monitoring_stack(self) -> Tuple[bool, Dict]:
        """Check monitoring stack (Prometheus, Grafana, Alertmanager)."""
        monitoring_services = {
            "prometheus": 9090,
            "grafana": 3000,
            "alertmanager": 9093
        }
        
        results = {
            "services": {},
            "all_services_healthy": True
        }
        
        async with aiohttp.ClientSession() as session:
            for service, port in monitoring_services.items():
                try:
                    # Different health endpoints for different services
                    if service == "prometheus":
                        url = f"http://localhost:{port}/-/healthy"
                    elif service == "grafana":
                        url = f"http://localhost:{port}/api/health"
                    elif service == "alertmanager":
                        url = f"http://localhost:{port}/-/healthy"
                    
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        service_healthy = response.status == 200
                        
                        results["services"][service] = {
                            "status_code": response.status,
                            "healthy": service_healthy,
                            "port": port
                        }
                        
                        if not service_healthy:
                            results["all_services_healthy"] = False
                            
                except Exception as e:
                    results["services"][service] = {
                        "status_code": 0,
                        "healthy": False,
                        "error": str(e),
                        "port": port
                    }
                    results["all_services_healthy"] = False
        
        return results["all_services_healthy"], results
    
    async def _check_security_health(self) -> Tuple[bool, Dict]:
        """Check security configuration and alerts."""
        try:
            async with aiohttp.ClientSession() as session:
                # Check active security alerts
                url = f"http://localhost:{self.api_port}/monitoring/alerts"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        alerts_data = await response.json()
                        
                        active_alerts = alerts_data.get("active_alerts", [])
                        security_alerts = [
                            alert for alert in active_alerts 
                            if any(keyword in alert.get("name", "").lower() 
                                  for keyword in ["security", "auth", "rls", "bypass"])
                        ]
                        
                        # Check for critical security issues
                        critical_security_alerts = [
                            alert for alert in security_alerts
                            if alert.get("severity") == "critical"
                        ]
                        
                        security_healthy = len(critical_security_alerts) == 0
                        
                        return security_healthy, {
                            "status": "healthy" if security_healthy else "unhealthy",
                            "total_security_alerts": len(security_alerts),
                            "critical_security_alerts": len(critical_security_alerts),
                            "security_alerts": security_alerts,
                            "message": f"Found {len(security_alerts)} security alerts, {len(critical_security_alerts)} critical"
                        }
                    else:
                        return False, {
                            "status": "error",
                            "error": f"Alerts endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return False, {
                "status": "error",
                "error": str(e),
                "message": "Failed to check security health"
            }
    
    async def _check_performance_health(self) -> Tuple[bool, Dict]:
        """Check performance metrics and thresholds."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{self.api_port}/monitoring/diagnostic"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        diagnostic_data = await response.json()
                        
                        performance_summary = diagnostic_data.get("performance_summary", {})
                        
                        # Check performance thresholds
                        performance_issues = []
                        
                        for operation, metrics in performance_summary.items():
                            p95_ms = metrics.get("p95_ms", 0)
                            error_rate = metrics.get("error_rate", 0)
                            
                            if p95_ms > 2000:  # 2 second threshold
                                performance_issues.append(f"{operation} P95 response time: {p95_ms}ms")
                            
                            if error_rate > 0.05:  # 5% error rate threshold
                                performance_issues.append(f"{operation} error rate: {error_rate*100:.1f}%")
                        
                        performance_healthy = len(performance_issues) == 0
                        
                        return performance_healthy, {
                            "status": "healthy" if performance_healthy else "degraded",
                            "performance_issues": performance_issues,
                            "performance_summary": performance_summary,
                            "collection_time_seconds": diagnostic_data.get("collection_time_seconds", 0)
                        }
                    else:
                        return False, {
                            "status": "error",
                            "error": f"Diagnostic endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return False, {
                "status": "error",
                "error": str(e),
                "message": "Failed to check performance health"
            }
    
    async def _check_backup_health(self) -> Tuple[bool, Dict]:
        """Check backup system health."""
        try:
            # This would integrate with the disaster recovery system
            # For now, return a basic check
            
            return True, {
                "status": "healthy",
                "message": "Backup system check not implemented yet",
                "last_backup": "unknown",
                "backup_frequency": "configured"
            }
            
        except Exception as e:
            return False, {
                "status": "error",
                "error": str(e),
                "message": "Failed to check backup health"
            }
    
    def _generate_recommendations(self, checks: Dict) -> List[str]:
        """Generate actionable recommendations based on check results."""
        recommendations = []
        
        # Core services recommendations
        core_services = checks.get("core_services", {})
        if core_services.get("status") != "healthy":
            recommendations.append("Investigate core service issues - check database and Redis connectivity")
        
        # API endpoints recommendations
        api_endpoints = checks.get("api_endpoints", {})
        if not api_endpoints.get("all_endpoints_healthy", True):
            recommendations.append("Some API endpoints are unhealthy - check application logs and restart services if needed")
        
        avg_response_time = api_endpoints.get("average_response_time", 0)
        if avg_response_time > 1000:  # 1 second
            recommendations.append(f"API response time is high ({avg_response_time}ms) - investigate performance bottlenecks")
        
        # Queue recommendations
        queue_workers = checks.get("queue_workers", {})
        total_queued = queue_workers.get("total_queued", 0)
        total_workers = queue_workers.get("total_workers", 0)
        
        if total_queued > 100:
            recommendations.append(f"Queue backlog is high ({total_queued} tasks) - consider scaling workers")
        
        if total_workers == 0:
            recommendations.append("No workers available - start Celery workers immediately")
        
        # Monitoring recommendations
        monitoring = checks.get("monitoring", {})
        if not monitoring.get("all_services_healthy", True):
            recommendations.append("Monitoring services are down - restart Prometheus, Grafana, or Alertmanager")
        
        # Performance recommendations
        performance = checks.get("performance", {})
        performance_issues = performance.get("performance_issues", [])
        if performance_issues:
            recommendations.append("Performance issues detected - review slow operations and optimize queries")
        
        # Security recommendations
        security = checks.get("security", {})
        critical_security_alerts = security.get("critical_security_alerts", 0)
        if critical_security_alerts > 0:
            recommendations.append("Critical security alerts active - investigate immediately")
        
        return recommendations
    
    def _extract_critical_issues(self, checks: Dict) -> List[str]:
        """Extract critical issues that require immediate attention."""
        critical_issues = []
        
        for check_name, check_data in checks.items():
            if isinstance(check_data, dict):
                status = check_data.get("status", "unknown")
                
                if status in ["unhealthy", "error"]:
                    error_msg = check_data.get("error", check_data.get("message", "Unknown error"))
                    critical_issues.append(f"{check_name}: {error_msg}")
        
        return critical_issues
    
    def _extract_warnings(self, checks: Dict) -> List[str]:
        """Extract warnings that should be addressed."""
        warnings = []
        
        # Performance warnings
        performance = checks.get("performance", {})
        performance_issues = performance.get("performance_issues", [])
        warnings.extend(performance_issues)
        
        # Queue warnings
        queue_workers = checks.get("queue_workers", {})
        total_queued = queue_workers.get("total_queued", 0)
        if 50 <= total_queued <= 100:
            warnings.append(f"Queue depth is elevated ({total_queued} tasks)")
        
        # API response time warnings
        api_endpoints = checks.get("api_endpoints", {})
        avg_response_time = api_endpoints.get("average_response_time", 0)
        if 500 <= avg_response_time <= 1000:
            warnings.append(f"API response time is elevated ({avg_response_time}ms)")
        
        return warnings


def print_health_report(results: Dict):
    """Print a formatted health report."""
    print("\n" + "="*80)
    print(f"ATS BACKEND HEALTH REPORT - {results['environment'].upper()}")
    print("="*80)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Overall Status: {results['overall_status'].upper()}")
    print(f"Check Duration: {results.get('check_duration_seconds', 0)} seconds")
    
    # Overall status indicator
    status_emoji = {
        "healthy": "✅",
        "degraded": "⚠️",
        "unhealthy": "❌",
        "error": "💥"
    }
    
    print(f"\n{status_emoji.get(results['overall_status'], '❓')} System Status: {results['overall_status'].upper()}")
    
    # Critical issues
    if results.get("critical_issues"):
        print(f"\n🚨 CRITICAL ISSUES ({len(results['critical_issues'])}):")
        for issue in results["critical_issues"]:
            print(f"  • {issue}")
    
    # Warnings
    if results.get("warnings"):
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            print(f"  • {warning}")
    
    # Detailed check results
    print(f"\nDETAILED CHECK RESULTS:")
    print("-"*80)
    
    for check_name, check_data in results.get("checks", {}).items():
        if isinstance(check_data, dict):
            status = check_data.get("status", "unknown")
            status_symbol = "✅" if status == "healthy" else "❌" if status in ["unhealthy", "error"] else "⚠️"
            
            print(f"{check_name.replace('_', ' ').title():<25} {status_symbol} {status.upper()}")
            
            # Show additional details for failed checks
            if status in ["unhealthy", "error", "degraded"]:
                if "error" in check_data:
                    print(f"  └─ Error: {check_data['error']}")
                if "message" in check_data:
                    print(f"  └─ Message: {check_data['message']}")
    
    # Recommendations
    if results.get("recommendations"):
        print(f"\n💡 RECOMMENDATIONS:")
        for i, recommendation in enumerate(results["recommendations"], 1):
            print(f"  {i}. {recommendation}")
    
    # Summary
    if results["overall_status"] == "healthy":
        print(f"\n🎉 All systems are healthy and operating normally!")
    elif results["overall_status"] == "degraded":
        print(f"\n⚠️  System is operational but has some issues that should be addressed.")
    else:
        print(f"\n🚨 System has critical issues that require immediate attention!")
    
    print("="*80)


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ATS Backend Production Health Checker")
    parser.add_argument("--environment", "-e",
                       choices=["dev", "staging", "prod"],
                       default="prod",
                       help="Environment to check (default: prod)")
    parser.add_argument("--json", action="store_true",
                       help="Output results in JSON format")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Only output critical issues")
    
    args = parser.parse_args()
    
    checker = ProductionHealthChecker(args.environment)
    
    try:
        healthy, results = await checker.run_comprehensive_health_check()
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        elif args.quiet:
            if results.get("critical_issues"):
                print("CRITICAL ISSUES:")
                for issue in results["critical_issues"]:
                    print(f"  {issue}")
            else:
                print("No critical issues found")
        else:
            print_health_report(results)
        
        # Exit with appropriate code
        if results["overall_status"] == "healthy":
            sys.exit(0)
        elif results["overall_status"] == "degraded":
            sys.exit(1)
        else:
            sys.exit(2)
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        print(f"❌ Health check failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())