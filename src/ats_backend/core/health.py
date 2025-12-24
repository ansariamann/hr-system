"""Comprehensive health check system for all services."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import psutil
import structlog

from .database import get_db
from .redis import get_redis_client
from .config import settings

logger = structlog.get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheck:
    """Individual health check result."""
    
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
        details: Dict[str, Any] = None,
        response_time_ms: float = None
    ):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.response_time_ms = response_time_ms
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert health check to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp.isoformat()
        }


class SystemHealthChecker:
    """Comprehensive system health checker."""
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
    
    async def check_database_health(self) -> HealthCheck:
        """Check PostgreSQL database health."""
        start_time = datetime.utcnow()
        
        try:
            db = next(get_db())
            
            # Test basic connectivity
            result = db.execute("SELECT 1").fetchone()
            
            # Test RLS functionality
            db.execute("SELECT current_setting('app.current_client_id', true)")
            
            # Check connection pool status
            pool_info = {
                "pool_size": db.bind.pool.size(),
                "checked_in": db.bind.pool.checkedin(),
                "checked_out": db.bind.pool.checkedout(),
                "invalid": db.bind.pool.invalid()
            }
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            db.close()
            
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                details=pool_info,
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                response_time_ms=response_time
            )
    
    async def check_redis_health(self) -> HealthCheck:
        """Check Redis health."""
        start_time = datetime.utcnow()
        
        try:
            redis_client = get_redis_client()
            
            # Test basic connectivity
            await redis_client.ping()
            
            # Test read/write operations
            test_key = "health_check_test"
            await redis_client.set(test_key, "test_value", ex=10)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            # Get Redis info
            info = await redis_client.info()
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
                details={
                    "version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                response_time_ms=response_time
            )
    
    async def check_celery_health(self) -> HealthCheck:
        """Check Celery worker health."""
        start_time = datetime.utcnow()
        
        try:
            from ..workers.celery_app import celery_app, task_monitor
            
            # Get worker statistics
            worker_stats = task_monitor.get_worker_stats()
            active_tasks = task_monitor.get_active_tasks()
            queue_info = task_monitor.get_queue_lengths()
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Determine health status
            total_workers = worker_stats.get("total_workers", 0)
            total_queued = queue_info.get("total_queued", 0)
            
            if total_workers == 0:
                status = HealthStatus.UNHEALTHY
                message = "No Celery workers available"
            elif total_queued > 100:
                status = HealthStatus.DEGRADED
                message = f"High queue backlog: {total_queued} tasks"
            else:
                status = HealthStatus.HEALTHY
                message = "Celery workers operational"
            
            return HealthCheck(
                name="celery",
                status=status,
                message=message,
                details={
                    "total_workers": total_workers,
                    "active_tasks": active_tasks.get("total_active", 0),
                    "queued_tasks": total_queued,
                    "queue_breakdown": queue_info.get("queues", {}),
                    "worker_stats": worker_stats
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="celery",
                status=HealthStatus.UNHEALTHY,
                message=f"Celery health check failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                response_time_ms=response_time
            )
    
    async def check_system_resources(self) -> HealthCheck:
        """Check system resource usage."""
        start_time = datetime.utcnow()
        
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Determine health status based on thresholds
            issues = []
            
            if cpu_percent > 90:
                issues.append(f"High CPU usage: {cpu_percent}%")
            if memory.percent > 90:
                issues.append(f"High memory usage: {memory.percent}%")
            if (disk.used / disk.total) * 100 > 95:
                issues.append(f"High disk usage: {(disk.used / disk.total) * 100:.1f}%")
            
            if issues:
                status = HealthStatus.DEGRADED if len(issues) == 1 else HealthStatus.UNHEALTHY
                message = "; ".join(issues)
            else:
                status = HealthStatus.HEALTHY
                message = "System resources within normal limits"
            
            return HealthCheck(
                name="system_resources",
                status=status,
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_percent": (disk.used / disk.total) * 100,
                    "disk_free_gb": disk.free / (1024**3),
                    "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message=f"System resource check failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                response_time_ms=response_time
            )
    
    async def check_file_storage(self) -> HealthCheck:
        """Check file storage health."""
        start_time = datetime.utcnow()
        
        try:
            import os
            from pathlib import Path
            
            storage_path = Path(settings.email_storage_path)
            
            # Check if storage directory exists and is writable
            if not storage_path.exists():
                storage_path.mkdir(parents=True, exist_ok=True)
            
            # Test write permissions
            test_file = storage_path / "health_check_test.txt"
            test_file.write_text("health check test")
            test_file.unlink()
            
            # Get storage statistics
            stat = os.statvfs(storage_path)
            total_space = stat.f_frsize * stat.f_blocks
            free_space = stat.f_frsize * stat.f_bavail
            used_space = total_space - free_space
            used_percent = (used_space / total_space) * 100
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Determine health status
            if used_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Storage critically full: {used_percent:.1f}% used"
            elif used_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"Storage getting full: {used_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = "File storage operational"
            
            return HealthCheck(
                name="file_storage",
                status=status,
                message=message,
                details={
                    "storage_path": str(storage_path),
                    "total_space_gb": total_space / (1024**3),
                    "free_space_gb": free_space / (1024**3),
                    "used_percent": used_percent
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="file_storage",
                status=HealthStatus.UNHEALTHY,
                message=f"File storage check failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                response_time_ms=response_time
            )
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive results."""
        logger.info("Starting comprehensive health check")
        
        start_time = datetime.utcnow()
        
        # Run all health checks concurrently
        checks = await asyncio.gather(
            self.check_database_health(),
            self.check_redis_health(),
            self.check_celery_health(),
            self.check_system_resources(),
            self.check_file_storage(),
            return_exceptions=True
        )
        
        # Process results
        health_checks = []
        overall_status = HealthStatus.HEALTHY
        
        for check in checks:
            if isinstance(check, Exception):
                # Handle unexpected errors in health checks
                health_checks.append(HealthCheck(
                    name="unknown",
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(check)}",
                    details={"error": str(check), "error_type": type(check).__name__}
                ))
                overall_status = HealthStatus.UNHEALTHY
            else:
                health_checks.append(check)
                
                # Determine overall status
                if check.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif check.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                elif check.status == HealthStatus.UNKNOWN and overall_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                    overall_status = HealthStatus.DEGRADED
        
        total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Create comprehensive health report
        health_report = {
            "overall_status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "total_check_time_ms": total_time,
            "checks": [check.to_dict() for check in health_checks],
            "summary": {
                "healthy_checks": len([c for c in health_checks if c.status == HealthStatus.HEALTHY]),
                "degraded_checks": len([c for c in health_checks if c.status == HealthStatus.DEGRADED]),
                "unhealthy_checks": len([c for c in health_checks if c.status == HealthStatus.UNHEALTHY]),
                "unknown_checks": len([c for c in health_checks if c.status == HealthStatus.UNKNOWN]),
                "total_checks": len(health_checks)
            }
        }
        
        logger.info(
            "Health check completed",
            overall_status=overall_status.value,
            total_time_ms=total_time,
            healthy_checks=health_report["summary"]["healthy_checks"],
            degraded_checks=health_report["summary"]["degraded_checks"],
            unhealthy_checks=health_report["summary"]["unhealthy_checks"]
        )
        
        return health_report


# Global health checker instance
health_checker = SystemHealthChecker()