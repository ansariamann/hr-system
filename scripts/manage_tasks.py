#!/usr/bin/env python3
"""
Celery Task Management Utility

This script provides utilities for managing Celery tasks including:
- Listing active tasks
- Cancelling tasks
- Retrying failed tasks
- Getting task status
- Purging queues
"""

import sys
import argparse
from typing import Dict, Any, Optional
from uuid import UUID
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


def list_active_tasks() -> None:
    """List all active tasks."""
    try:
        from ats_backend.workers.celery_app import task_monitor
        
        active_tasks = task_monitor.get_active_tasks()
        
        if "error" in active_tasks:
            print(f"❌ Error getting active tasks: {active_tasks['error']}")
            return
        
        total_active = active_tasks.get("total_active", 0)
        print(f"📋 Active Tasks: {total_active}")
        
        if total_active == 0:
            print("   No active tasks")
            return
        
        workers = active_tasks.get("active_tasks", {})
        for worker_name, tasks in workers.items():
            print(f"\n🔧 Worker: {worker_name}")
            for task in tasks:
                task_id = task.get("id", "unknown")
                task_name = task.get("name", "unknown")
                args = task.get("args", [])
                kwargs = task.get("kwargs", {})
                
                print(f"   📝 Task ID: {task_id}")
                print(f"      Name: {task_name}")
                print(f"      Args: {args}")
                print(f"      Kwargs: {kwargs}")
                print()
        
    except Exception as e:
        print(f"❌ Error listing active tasks: {str(e)}")
        logger.error("Failed to list active tasks", error=str(e))


def get_task_status(task_id: str) -> None:
    """Get detailed status of a specific task."""
    try:
        from ats_backend.workers.celery_app import task_monitor
        
        task_info = task_monitor.get_task_info(task_id)
        
        if "error" in task_info:
            print(f"❌ Error getting task status: {task_info['error']}")
            return
        
        print(f"📝 Task Status: {task_id}")
        print(f"   State: {task_info.get('state', 'unknown')}")
        print(f"   Ready: {task_info.get('ready', False)}")
        print(f"   Successful: {task_info.get('successful', 'N/A')}")
        print(f"   Failed: {task_info.get('failed', 'N/A')}")
        
        if task_info.get("result"):
            print(f"   Result: {task_info['result']}")
        
        if task_info.get("error"):
            print(f"   Error: {task_info['error']}")
        
        if task_info.get("traceback"):
            print(f"   Traceback: {task_info['traceback']}")
        
    except Exception as e:
        print(f"❌ Error getting task status: {str(e)}")
        logger.error("Failed to get task status", task_id=task_id, error=str(e))


def cancel_task(task_id: str) -> None:
    """Cancel a running task."""
    try:
        from ats_backend.workers.celery_app import celery_app
        
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        
        print(f"✅ Task {task_id} has been cancelled")
        logger.info("Task cancelled", task_id=task_id)
        
    except Exception as e:
        print(f"❌ Error cancelling task: {str(e)}")
        logger.error("Failed to cancel task", task_id=task_id, error=str(e))


def list_queues() -> None:
    """List queue information."""
    try:
        from ats_backend.workers.celery_app import task_monitor
        
        queue_info = task_monitor.get_queue_lengths()
        
        if "error" in queue_info:
            print(f"❌ Error getting queue info: {queue_info['error']}")
            return
        
        total_queued = queue_info.get("total_queued", 0)
        print(f"📊 Queue Status (Total: {total_queued} tasks)")
        
        queues = queue_info.get("queues", {})
        for queue_name, length in queues.items():
            status_icon = "🔴" if length > 10 else "🟡" if length > 0 else "🟢"
            print(f"   {status_icon} {queue_name}: {length} tasks")
        
    except Exception as e:
        print(f"❌ Error listing queues: {str(e)}")
        logger.error("Failed to list queues", error=str(e))


def purge_queue(queue_name: str) -> None:
    """Purge all tasks from a specific queue."""
    try:
        from ats_backend.workers.celery_app import celery_app
        
        # Purge the queue
        celery_app.control.purge()
        
        print(f"✅ Queue '{queue_name}' has been purged")
        logger.info("Queue purged", queue_name=queue_name)
        
    except Exception as e:
        print(f"❌ Error purging queue: {str(e)}")
        logger.error("Failed to purge queue", queue_name=queue_name, error=str(e))


def list_workers() -> None:
    """List worker information."""
    try:
        from ats_backend.workers.celery_app import task_monitor
        
        worker_stats = task_monitor.get_worker_stats()
        
        if "error" in worker_stats:
            print(f"❌ Error getting worker stats: {worker_stats['error']}")
            return
        
        total_workers = worker_stats.get("total_workers", 0)
        print(f"🔧 Workers: {total_workers}")
        
        if total_workers == 0:
            print("   No workers available")
            return
        
        workers = worker_stats.get("workers", {})
        for worker_name, stats in workers.items():
            print(f"\n🔧 Worker: {worker_name}")
            
            # Basic stats
            if "pool" in stats:
                pool_stats = stats["pool"]
                print(f"   Processes: {pool_stats.get('processes', 'unknown')}")
                print(f"   Max Concurrency: {pool_stats.get('max-concurrency', 'unknown')}")
            
            if "rusage" in stats:
                rusage = stats["rusage"]
                print(f"   CPU Time: {rusage.get('utime', 0):.2f}s user, {rusage.get('stime', 0):.2f}s system")
                print(f"   Memory: {rusage.get('maxrss', 0)} KB")
            
            if "total" in stats:
                total_stats = stats["total"]
                for key, value in total_stats.items():
                    print(f"   {key.replace('_', ' ').title()}: {value}")
        
    except Exception as e:
        print(f"❌ Error listing workers: {str(e)}")
        logger.error("Failed to list workers", error=str(e))


def retry_failed_resume(client_id: str, job_id: str, user_id: Optional[str] = None) -> None:
    """Retry a failed resume processing job."""
    try:
        from ats_backend.workers.resume_tasks import reprocess_failed_resume
        
        # Queue the retry task
        task = reprocess_failed_resume.delay(client_id, job_id, user_id)
        
        print(f"✅ Resume retry task queued: {task.id}")
        print(f"   Client ID: {client_id}")
        print(f"   Job ID: {job_id}")
        print(f"   User ID: {user_id or 'None'}")
        
        logger.info(
            "Resume retry task queued",
            task_id=task.id,
            client_id=client_id,
            job_id=job_id,
            user_id=user_id
        )
        
    except Exception as e:
        print(f"❌ Error retrying failed resume: {str(e)}")
        logger.error(
            "Failed to retry resume",
            client_id=client_id,
            job_id=job_id,
            error=str(e)
        )


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Celery Task Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_tasks.py list-active
  python manage_tasks.py status abc123-task-id
  python manage_tasks.py cancel abc123-task-id
  python manage_tasks.py list-queues
  python manage_tasks.py list-workers
  python manage_tasks.py retry-resume client-id job-id
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List active tasks
    subparsers.add_parser("list-active", help="List all active tasks")
    
    # Get task status
    status_parser = subparsers.add_parser("status", help="Get task status")
    status_parser.add_argument("task_id", help="Task ID to check")
    
    # Cancel task
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a running task")
    cancel_parser.add_argument("task_id", help="Task ID to cancel")
    
    # List queues
    subparsers.add_parser("list-queues", help="List queue information")
    
    # Purge queue
    purge_parser = subparsers.add_parser("purge-queue", help="Purge all tasks from a queue")
    purge_parser.add_argument("queue_name", help="Queue name to purge")
    
    # List workers
    subparsers.add_parser("list-workers", help="List worker information")
    
    # Retry failed resume
    retry_parser = subparsers.add_parser("retry-resume", help="Retry a failed resume processing job")
    retry_parser.add_argument("client_id", help="Client ID")
    retry_parser.add_argument("job_id", help="Resume job ID")
    retry_parser.add_argument("--user-id", help="User ID (optional)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🚀 ATS Backend Task Management")
    print("=" * 40)
    
    try:
        if args.command == "list-active":
            list_active_tasks()
        elif args.command == "status":
            get_task_status(args.task_id)
        elif args.command == "cancel":
            cancel_task(args.task_id)
        elif args.command == "list-queues":
            list_queues()
        elif args.command == "purge-queue":
            purge_queue(args.queue_name)
        elif args.command == "list-workers":
            list_workers()
        elif args.command == "retry-resume":
            retry_failed_resume(args.client_id, args.job_id, args.user_id)
        else:
            print(f"❌ Unknown command: {args.command}")
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        logger.error("Unexpected error in task management", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()