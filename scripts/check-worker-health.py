#!/usr/bin/env python3
"""
Celery Worker Health Check Script

This script checks the health of Celery workers and provides detailed status information.
"""

import sys
import time
from typing import Dict, Any
import structlog

# Setup logging
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


def check_redis_connectivity() -> bool:
    """Check if Redis is accessible."""
    try:
        from ats_backend.core.redis import get_redis_client
        
        redis_client = get_redis_client()
        redis_client.ping()
        logger.info("Redis connectivity check passed")
        return True
        
    except Exception as e:
        logger.error("Redis connectivity check failed", error=str(e))
        return False


def check_celery_app() -> bool:
    """Check if Celery app can be imported and configured."""
    try:
        from ats_backend.workers.celery_app import celery_app
        
        # Check basic configuration
        broker_url = celery_app.conf.broker_url
        result_backend = celery_app.conf.result_backend
        
        logger.info(
            "Celery app check passed",
            broker_url=broker_url,
            result_backend=result_backend
        )
        return True
        
    except Exception as e:
        logger.error("Celery app check failed", error=str(e))
        return False


def check_task_imports() -> bool:
    """Check if all tasks can be imported."""
    try:
        from ats_backend.workers.resume_tasks import (
            process_resume_file,
            batch_process_resumes,
            reprocess_failed_resume,
            validate_resume_parsing
        )
        from ats_backend.workers.email_tasks import (
            process_email_message,
            cleanup_old_files,
            cleanup_failed_jobs,
            validate_email_format,
            cleanup_failed_jobs_all_clients,
            health_check_workers,
            monitor_system_performance
        )
        
        logger.info("Task imports check passed")
        return True
        
    except Exception as e:
        logger.error("Task imports check failed", error=str(e))
        return False


def check_worker_status() -> Dict[str, Any]:
    """Check the status of active workers."""
    try:
        from ats_backend.workers.celery_app import task_monitor
        
        worker_stats = task_monitor.get_worker_stats()
        active_tasks = task_monitor.get_active_tasks()
        queue_info = task_monitor.get_queue_lengths()
        
        status = {
            "workers": worker_stats,
            "active_tasks": active_tasks,
            "queues": queue_info,
            "healthy": True
        }
        
        # Check for issues
        issues = []
        
        if worker_stats.get("total_workers", 0) == 0:
            issues.append("No workers are currently running")
            status["healthy"] = False
        
        if "error" in worker_stats:
            issues.append(f"Worker stats error: {worker_stats['error']}")
            status["healthy"] = False
        
        if "error" in active_tasks:
            issues.append(f"Active tasks error: {active_tasks['error']}")
            status["healthy"] = False
        
        if "error" in queue_info:
            issues.append(f"Queue info error: {queue_info['error']}")
            status["healthy"] = False
        
        status["issues"] = issues
        
        logger.info(
            "Worker status check completed",
            healthy=status["healthy"],
            issues_count=len(issues)
        )
        
        return status
        
    except Exception as e:
        logger.error("Worker status check failed", error=str(e))
        return {
            "healthy": False,
            "error": str(e),
            "issues": [f"Status check failed: {str(e)}"]
        }


def test_task_execution() -> bool:
    """Test if tasks can be queued and executed."""
    try:
        from ats_backend.workers.email_tasks import validate_email_format
        
        # Test email validation task (lightweight test)
        test_email_data = {
            "message_id": "test-health-check-123",
            "sender": "test@example.com",
            "subject": "Health Check Test",
            "body": "This is a health check test email",
            "attachments": []
        }
        
        # Queue the task
        task = validate_email_format.delay(test_email_data)
        
        # Wait for result with timeout
        result = task.get(timeout=10)
        
        if result and "valid" in result:
            logger.info("Task execution test passed", task_id=task.id)
            return True
        else:
            logger.error("Task execution test failed - invalid result", result=result)
            return False
            
    except Exception as e:
        logger.error("Task execution test failed", error=str(e))
        return False


def main():
    """Run comprehensive health check."""
    print("=" * 60)
    print("ATS Backend Celery Worker Health Check")
    print("=" * 60)
    
    checks = [
        ("Redis Connectivity", check_redis_connectivity),
        ("Celery App Configuration", check_celery_app),
        ("Task Imports", check_task_imports),
    ]
    
    passed_checks = 0
    total_checks = len(checks)
    
    # Run basic checks
    for check_name, check_func in checks:
        print(f"\n🔍 Running {check_name}...")
        try:
            if check_func():
                print(f"✅ {check_name}: PASSED")
                passed_checks += 1
            else:
                print(f"❌ {check_name}: FAILED")
        except Exception as e:
            print(f"❌ {check_name}: ERROR - {str(e)}")
    
    # Check worker status
    print(f"\n🔍 Checking Worker Status...")
    worker_status = check_worker_status()
    
    if worker_status.get("healthy", False):
        print("✅ Worker Status: HEALTHY")
        
        # Display worker information
        workers = worker_status.get("workers", {})
        if "workers" in workers:
            print(f"   Active Workers: {workers.get('total_workers', 0)}")
        
        active_tasks = worker_status.get("active_tasks", {})
        if "total_active" in active_tasks:
            print(f"   Active Tasks: {active_tasks['total_active']}")
        
        queues = worker_status.get("queues", {})
        if "queues" in queues:
            for queue_name, length in queues["queues"].items():
                print(f"   Queue '{queue_name}': {length} tasks")
        
        passed_checks += 1
    else:
        print("❌ Worker Status: UNHEALTHY")
        issues = worker_status.get("issues", [])
        for issue in issues:
            print(f"   - {issue}")
    
    total_checks += 1
    
    # Test task execution if workers are available
    if worker_status.get("healthy", False):
        print(f"\n🔍 Testing Task Execution...")
        if test_task_execution():
            print("✅ Task Execution: PASSED")
            passed_checks += 1
        else:
            print("❌ Task Execution: FAILED")
        total_checks += 1
    else:
        print(f"\n⚠️  Skipping Task Execution test (no workers available)")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Health Check Summary: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        print("🎉 All checks passed! Celery worker system is healthy.")
        sys.exit(0)
    else:
        print("⚠️  Some checks failed. Please review the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()