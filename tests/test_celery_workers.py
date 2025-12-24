"""Tests for Celery worker system."""

import pytest
import tempfile
import os
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch
from typing import Dict, Any

from ats_backend.workers.celery_app import celery_app, task_monitor
from ats_backend.workers.email_tasks import (
    validate_email_format,
    health_check_workers,
    monitor_system_performance
)
from ats_backend.workers.resume_tasks import validate_resume_parsing


class TestCeleryConfiguration:
    """Test Celery configuration and setup."""
    
    def test_celery_app_configuration(self):
        """Test that Celery app is properly configured."""
        # Check basic configuration
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]
        assert celery_app.conf.result_serializer == "json"
        
        # Check task routing
        assert "ats_backend.workers.resume_tasks.*" in celery_app.conf.task_routes
        assert "ats_backend.workers.email_tasks.*" in celery_app.conf.task_routes
        
        # Check retry configuration
        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.task_reject_on_worker_lost is True
        
        # Check time limits
        assert celery_app.conf.task_soft_time_limit == 600
        assert celery_app.conf.task_time_limit == 900
    
    def test_task_autodiscovery(self):
        """Test that tasks are properly autodiscovered."""
        # Get registered tasks
        registered_tasks = list(celery_app.tasks.keys())
        
        # Check that our tasks are registered
        expected_tasks = [
            "validate_email_format",
            "health_check_workers",
            "monitor_system_performance",
            "validate_resume_parsing",
            "process_resume_file",
            "cleanup_old_files"
        ]
        
        for task_name in expected_tasks:
            assert any(task_name in registered_task for registered_task in registered_tasks), \
                f"Task {task_name} not found in registered tasks"


class TestTaskMonitoring:
    """Test task monitoring functionality."""
    
    def test_task_monitor_initialization(self):
        """Test that task monitor is properly initialized."""
        assert task_monitor is not None
        assert hasattr(task_monitor, 'get_task_info')
        assert hasattr(task_monitor, 'get_active_tasks')
        assert hasattr(task_monitor, 'get_worker_stats')
        assert hasattr(task_monitor, 'get_queue_lengths')
    
    def test_get_task_info_invalid_id(self):
        """Test getting info for invalid task ID."""
        task_info = task_monitor.get_task_info("invalid-task-id")
        
        assert "task_id" in task_info
        assert task_info["task_id"] == "invalid-task-id"
        assert "state" in task_info
    
    def test_get_active_tasks(self):
        """Test getting active tasks information."""
        active_tasks = task_monitor.get_active_tasks()
        
        assert "total_active" in active_tasks
        assert "timestamp" in active_tasks
        assert isinstance(active_tasks["total_active"], int)
    
    def test_get_worker_stats(self):
        """Test getting worker statistics."""
        worker_stats = task_monitor.get_worker_stats()
        
        assert "total_workers" in worker_stats
        assert "timestamp" in worker_stats
        assert isinstance(worker_stats["total_workers"], int)
    
    def test_get_queue_lengths(self):
        """Test getting queue length information."""
        queue_info = task_monitor.get_queue_lengths()
        
        assert "total_queued" in queue_info
        assert "timestamp" in queue_info
        assert isinstance(queue_info["total_queued"], int)


class TestEmailTasks:
    """Test email processing tasks."""
    
    def test_validate_email_format_valid_email(self):
        """Test email validation with valid email data."""
        # Use eager mode for testing
        celery_app.conf.task_always_eager = True
        
        email_data = {
            "message_id": "test-123",
            "sender": "test@example.com",
            "subject": "Test Email",
            "body": "This is a test email",
            "attachments": []
        }
        
        result = validate_email_format.delay(email_data)
        task_result = result.get()
        
        assert task_result["valid"] is True
        assert task_result["message_id"] == "test-123"
        assert task_result["attachment_count"] == 0
        assert "task_id" in task_result
    
    def test_validate_email_format_invalid_email(self):
        """Test email validation with invalid email data."""
        celery_app.conf.task_always_eager = True
        
        # Missing required fields
        email_data = {
            "message_id": "test-456"
            # Missing sender, subject, body, attachments
        }
        
        result = validate_email_format.delay(email_data)
        task_result = result.get()
        
        assert task_result["valid"] is False
        assert len(task_result["errors"]) > 0
        assert "task_id" in task_result
    
    def test_health_check_workers(self):
        """Test worker health check task."""
        celery_app.conf.task_always_eager = True
        
        result = health_check_workers.delay()
        task_result = result.get()
        
        assert "healthy" in task_result
        assert "status" in task_result
        assert "summary" in task_result
        assert "task_id" in task_result
        assert isinstance(task_result["healthy"], bool)
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_monitor_system_performance(self, mock_disk, mock_memory, mock_cpu):
        """Test system performance monitoring task."""
        celery_app.conf.task_always_eager = True
        
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0, available=8*1024**3)
        mock_disk.return_value = Mock(used=100*1024**3, total=500*1024**3, free=400*1024**3)
        
        result = monitor_system_performance.delay()
        task_result = result.get()
        
        assert "system" in task_result
        assert "celery" in task_result
        assert "alerts" in task_result
        assert "timestamp" in task_result
        assert "task_id" in task_result
        
        # Check system metrics
        system_metrics = task_result["system"]
        assert system_metrics["cpu_percent"] == 50.0
        assert system_metrics["memory_percent"] == 60.0
        assert system_metrics["disk_percent"] == 20.0  # 100/500 * 100


class TestResumeTasks:
    """Test resume processing tasks."""
    
    def test_validate_resume_parsing_nonexistent_file(self):
        """Test resume parsing validation with nonexistent file."""
        celery_app.conf.task_always_eager = True
        
        result = validate_resume_parsing.delay("/nonexistent/file.pdf")
        task_result = result.get()
        
        assert task_result["success"] is False
        assert "message" in task_result
        assert "task_id" in task_result
        assert "Parsing failed" in task_result["message"]
    
    def test_validate_resume_parsing_with_expected_fields(self):
        """Test resume parsing validation with expected fields."""
        celery_app.conf.task_always_eager = True
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(b"dummy pdf content")
            temp_path = temp_file.name
        
        try:
            expected_fields = {
                "parsing_method": "pdf_text",
                "skills_count": 0
            }
            
            result = validate_resume_parsing.delay(temp_path, expected_fields)
            task_result = result.get()
            
            # Should fail because it's not a real PDF
            assert task_result["success"] is False
            assert "task_id" in task_result
            
        finally:
            os.unlink(temp_path)


class TestTaskRetryLogic:
    """Test task retry and error handling."""
    
    def test_email_task_retry_configuration(self):
        """Test that email tasks have proper retry configuration."""
        from ats_backend.workers.email_tasks import EmailProcessingTask
        
        task_instance = EmailProcessingTask()
        
        assert task_instance.autoretry_for == (Exception,)
        assert task_instance.retry_kwargs["max_retries"] == 3
        assert task_instance.retry_kwargs["countdown"] == 60
        assert task_instance.retry_backoff is True
        assert task_instance.retry_jitter is True
    
    def test_resume_task_retry_configuration(self):
        """Test that resume tasks have proper retry configuration."""
        from ats_backend.workers.resume_tasks import ResumeProcessingTask
        
        task_instance = ResumeProcessingTask()
        
        assert task_instance.autoretry_for == (Exception,)
        assert task_instance.retry_kwargs["max_retries"] == 3
        assert task_instance.retry_kwargs["countdown"] == 120
        assert task_instance.retry_backoff is True
        assert task_instance.retry_jitter is True


class TestTaskIntegration:
    """Test task integration with other system components."""
    
    def test_task_logging_integration(self):
        """Test that tasks properly integrate with logging system."""
        celery_app.conf.task_always_eager = True
        
        # Test that tasks can be executed without logging errors
        email_data = {
            "message_id": "logging-test-123",
            "sender": "test@example.com",
            "subject": "Logging Test",
            "body": "Test logging integration",
            "attachments": []
        }
        
        result = validate_email_format.delay(email_data)
        task_result = result.get()
        
        # Should complete successfully
        assert task_result["valid"] is True
        assert "task_id" in task_result
    
    def test_task_database_integration_mock(self):
        """Test task database integration with mocked database."""
        celery_app.conf.task_always_eager = True
        
        # Test health check which uses task monitor (doesn't require DB)
        result = health_check_workers.delay()
        task_result = result.get()
        
        # Should complete successfully even without real database
        assert "healthy" in task_result
        assert "task_id" in task_result


class TestTaskErrorHandling:
    """Test task error handling and failure scenarios."""
    
    def test_task_failure_handling(self):
        """Test that task failures are properly handled."""
        celery_app.conf.task_always_eager = True
        
        # Test with invalid data that should cause validation errors
        invalid_email_data = {
            "message_id": None,  # Invalid message ID
            "sender": "invalid-email",  # Invalid email format
            "subject": "",  # Empty subject
            "body": None,  # Invalid body
            "attachments": "not-a-list"  # Invalid attachments format
        }
        
        result = validate_email_format.delay(invalid_email_data)
        task_result = result.get()
        
        # Should handle the error gracefully
        assert task_result["valid"] is False
        assert len(task_result["errors"]) > 0
        assert "task_id" in task_result
    
    def test_system_monitoring_error_handling(self):
        """Test system monitoring error handling."""
        celery_app.conf.task_always_eager = True
        
        with patch('psutil.cpu_percent', side_effect=Exception("CPU monitoring failed")):
            result = monitor_system_performance.delay()
            task_result = result.get()
            
            # Should handle the error gracefully
            assert "error" in task_result
            assert "task_id" in task_result
            assert "CPU monitoring failed" in task_result["error"]


@pytest.fixture(autouse=True)
def reset_celery_config():
    """Reset Celery configuration after each test."""
    yield
    # Reset to non-eager mode
    celery_app.conf.task_always_eager = False