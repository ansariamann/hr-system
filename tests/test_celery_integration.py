"""Integration tests for Celery worker system (without Redis dependency)."""

import pytest
from unittest.mock import Mock, patch
from ats_backend.workers.celery_app import celery_app, TaskMonitor


class TestCeleryIntegrationWithoutRedis:
    """Test Celery integration without requiring Redis."""
    
    def test_celery_app_imports(self):
        """Test that Celery app can be imported and configured."""
        assert celery_app is not None
        assert celery_app.conf.broker_url is not None
        assert celery_app.conf.result_backend is not None
    
    def test_task_registration(self):
        """Test that tasks are properly registered."""
        registered_tasks = list(celery_app.tasks.keys())
        
        # Check for key tasks
        expected_tasks = [
            "validate_email_format",
            "health_check_workers", 
            "monitor_system_performance",
            "process_resume_file",
            "cleanup_old_files"
        ]
        
        for expected_task in expected_tasks:
            found = any(expected_task in task for task in registered_tasks)
            assert found, f"Task {expected_task} not found in registered tasks"
    
    def test_task_monitor_methods(self):
        """Test that TaskMonitor has all required methods."""
        monitor = TaskMonitor()
        
        # Test method existence
        assert hasattr(monitor, 'get_task_info')
        assert hasattr(monitor, 'get_active_tasks')
        assert hasattr(monitor, 'get_worker_stats')
        assert hasattr(monitor, 'get_queue_lengths')
        
        # Test methods return proper structure even without Redis
        task_info = monitor.get_task_info("test-id")
        assert "task_id" in task_info
        
        active_tasks = monitor.get_active_tasks()
        assert "total_active" in active_tasks
        
        worker_stats = monitor.get_worker_stats()
        assert "total_workers" in worker_stats
        
        queue_info = monitor.get_queue_lengths()
        assert "total_queued" in queue_info
    
    def test_celery_configuration_values(self):
        """Test specific Celery configuration values."""
        conf = celery_app.conf
        
        # Test serialization settings
        assert conf.task_serializer == "json"
        assert conf.accept_content == ["json"]
        assert conf.result_serializer == "json"
        
        # Test worker settings
        assert conf.worker_prefetch_multiplier == 1
        assert conf.worker_max_tasks_per_child == 1000
        assert conf.worker_send_task_events is True
        
        # Test time limits
        assert conf.task_soft_time_limit == 600
        assert conf.task_time_limit == 900
        
        # Test retry settings
        assert conf.task_acks_late is True
        assert conf.task_reject_on_worker_lost is True
        
        # Test result backend settings
        assert conf.result_expires == 7200
        assert conf.result_persistent is True
        
        # Test timezone settings
        assert conf.timezone == "UTC"
        assert conf.enable_utc is True
    
    def test_task_routing_configuration(self):
        """Test task routing configuration."""
        routes = celery_app.conf.task_routes
        
        assert "ats_backend.workers.resume_tasks.*" in routes
        assert "ats_backend.workers.email_tasks.*" in routes
        
        resume_route = routes["ats_backend.workers.resume_tasks.*"]
        email_route = routes["ats_backend.workers.email_tasks.*"]
        
        assert resume_route["queue"] == "resume_processing"
        assert email_route["queue"] == "email_processing"
    
    def test_beat_schedule_configuration(self):
        """Test Celery Beat schedule configuration."""
        schedule = celery_app.conf.beat_schedule
        
        # Check for scheduled tasks
        assert "cleanup-old-files" in schedule
        assert "cleanup-failed-jobs" in schedule
        assert "health-check-workers" in schedule
        
        # Check task configurations
        cleanup_files = schedule["cleanup-old-files"]
        assert cleanup_files["task"] == "cleanup_old_files"
        assert cleanup_files["schedule"] == 86400.0  # Daily
        
        cleanup_jobs = schedule["cleanup-failed-jobs"]
        assert cleanup_jobs["task"] == "cleanup_failed_jobs_all_clients"
        assert cleanup_jobs["schedule"] == 3600.0  # Hourly
        
        health_check = schedule["health-check-workers"]
        assert health_check["task"] == "health_check_workers"
        assert health_check["schedule"] == 300.0  # Every 5 minutes
    
    def test_task_import_paths(self):
        """Test that task import paths are correct."""
        includes = celery_app.conf.include
        
        expected_includes = [
            "ats_backend.workers.resume_tasks",
            "ats_backend.workers.email_tasks"
        ]
        
        for expected in expected_includes:
            assert expected in includes
    
    @patch('ats_backend.workers.celery_app.logger')
    def test_signal_handlers(self, mock_logger):
        """Test that Celery signal handlers are properly configured."""
        from ats_backend.workers.celery_app import (
            task_prerun_handler,
            task_postrun_handler,
            task_failure_handler,
            task_retry_handler,
            worker_ready_handler
        )
        
        # Test signal handlers exist and are callable
        assert callable(task_prerun_handler)
        assert callable(task_postrun_handler)
        assert callable(task_failure_handler)
        assert callable(task_retry_handler)
        assert callable(worker_ready_handler)
        
        # Test handlers can be called without errors
        task_prerun_handler(
            sender="test_task",
            task_id="test-123",
            task=Mock(name="test_task"),
            args=[],
            kwargs={}
        )
        
        task_postrun_handler(
            sender="test_task",
            task_id="test-123",
            task=Mock(name="test_task"),
            args=[],
            kwargs={},
            retval="success",
            state="SUCCESS"
        )
        
        task_failure_handler(
            sender=Mock(name="test_task"),
            task_id="test-123",
            exception=Exception("test error"),
            traceback="test traceback",
            einfo=None
        )
        
        task_retry_handler(
            sender=Mock(name="test_task"),
            task_id="test-123",
            reason="test retry",
            einfo=None
        )
        
        worker_ready_handler(
            sender=Mock(hostname="test-worker")
        )


class TestTaskClassConfiguration:
    """Test task class configurations."""
    
    def test_email_processing_task_config(self):
        """Test EmailProcessingTask configuration."""
        from ats_backend.workers.email_tasks import EmailProcessingTask
        
        task = EmailProcessingTask()
        
        assert task.autoretry_for == (Exception,)
        assert task.retry_kwargs["max_retries"] == 3
        assert task.retry_kwargs["countdown"] == 60
        assert task.retry_backoff is True
        assert task.retry_backoff_max == 300
        assert task.retry_jitter is True
    
    def test_resume_processing_task_config(self):
        """Test ResumeProcessingTask configuration."""
        from ats_backend.workers.resume_tasks import ResumeProcessingTask
        
        task = ResumeProcessingTask()
        
        assert task.autoretry_for == (Exception,)
        assert task.retry_kwargs["max_retries"] == 3
        assert task.retry_kwargs["countdown"] == 120
        assert task.retry_backoff is True
        assert task.retry_backoff_max == 600
        assert task.retry_jitter is True
    
    def test_task_error_handlers(self):
        """Test task error handler methods."""
        from ats_backend.workers.email_tasks import EmailProcessingTask
        from ats_backend.workers.resume_tasks import ResumeProcessingTask
        
        email_task = EmailProcessingTask()
        resume_task = ResumeProcessingTask()
        
        # Test that error handler methods exist
        assert hasattr(email_task, 'on_failure')
        assert hasattr(email_task, 'on_retry')
        assert hasattr(resume_task, 'on_failure')
        assert hasattr(resume_task, 'on_retry')
        
        # Test that they're callable
        assert callable(email_task.on_failure)
        assert callable(email_task.on_retry)
        assert callable(resume_task.on_failure)
        assert callable(resume_task.on_retry)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])