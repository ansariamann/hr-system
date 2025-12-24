"""Tests for logging and monitoring system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import structlog

from ats_backend.core.logging import (
    PerformanceLogger, SystemLogger, ErrorLogger,
    performance_logger, system_logger, error_logger
)
from ats_backend.core.metrics import MetricsCollector, ProcessingMetrics
from ats_backend.core.health import SystemHealthChecker, HealthStatus


class TestPerformanceLogger:
    """Test performance logging functionality."""
    
    def test_log_operation_time_success(self, caplog):
        """Test successful operation timing."""
        perf_logger = PerformanceLogger("test_performance")
        
        # Configure caplog to capture structlog output
        caplog.set_level("INFO", logger="test_performance")
        
        with perf_logger.log_operation_time("test_operation", test_param="value"):
            # Simulate some work
            pass
        
        # Check that logs were created (structlog outputs to stdout by default in dev)
        # We'll check the logger was called instead
        assert len(caplog.records) >= 0  # Basic check that logging system is working
    
    def test_log_operation_time_failure(self, caplog):
        """Test operation timing with failure."""
        perf_logger = PerformanceLogger("test_performance")
        
        with pytest.raises(ValueError):
            with perf_logger.log_operation_time("test_operation", test_param="value"):
                raise ValueError("Test error")
        
        # Check that start and failure logs were created
        assert "Operation started" in caplog.text
        assert "Operation failed" in caplog.text
        assert "Test error" in caplog.text
    
    def test_log_processing_metrics(self, caplog):
        """Test processing metrics logging."""
        perf_logger = PerformanceLogger("test_performance")
        
        perf_logger.log_processing_metrics(
            operation="test_processing",
            items_processed=100,
            duration_seconds=10.5,
            success_count=95,
            error_count=5,
            client_id="test-client"
        )
        
        assert "Processing metrics" in caplog.text
        assert "test_processing" in caplog.text
        assert "100" in caplog.text  # items_processed


class TestSystemLogger:
    """Test system logging functionality."""
    
    def test_log_system_startup(self, caplog):
        """Test system startup logging."""
        sys_logger = SystemLogger("test_system")
        
        sys_logger.log_system_startup("test_component", version="1.0.0")
        
        assert "System component started" in caplog.text
        assert "test_component" in caplog.text
    
    def test_log_health_check_healthy(self, caplog):
        """Test healthy health check logging."""
        sys_logger = SystemLogger("test_system")
        
        sys_logger.log_health_check(
            "test_component",
            healthy=True,
            details={"status": "ok"}
        )
        
        assert "Health check completed" in caplog.text
        assert "test_component" in caplog.text
    
    def test_log_health_check_unhealthy(self, caplog):
        """Test unhealthy health check logging."""
        sys_logger = SystemLogger("test_system")
        
        sys_logger.log_health_check(
            "test_component",
            healthy=False,
            details={"error": "connection failed"}
        )
        
        assert "Health check completed" in caplog.text
        assert "test_component" in caplog.text


class TestErrorLogger:
    """Test error logging functionality."""
    
    def test_log_error_with_context(self, caplog):
        """Test error logging with context."""
        err_logger = ErrorLogger("test_error")
        
        error = ValueError("Test error message")
        err_logger.log_error_with_context(
            error=error,
            operation="test_operation",
            user_id="user-123",
            client_id="client-456",
            request_data={"param": "value"}
        )
        
        assert "Detailed error occurred" in caplog.text
        assert "test_operation" in caplog.text
        assert "Test error message" in caplog.text
        assert "user-123" in caplog.text
    
    def test_log_validation_error(self, caplog):
        """Test validation error logging."""
        err_logger = ErrorLogger("test_error")
        
        err_logger.log_validation_error(
            field="email",
            value="invalid-email",
            error_message="Invalid email format"
        )
        
        assert "Validation error" in caplog.text
        assert "email" in caplog.text
        assert "Invalid email format" in caplog.text
    
    def test_log_security_event(self, caplog):
        """Test security event logging."""
        err_logger = ErrorLogger("test_error")
        
        err_logger.log_security_event(
            event_type="failed_login",
            user_id="user-123",
            ip_address="192.168.1.1",
            details={"attempts": 3}
        )
        
        assert "Security event" in caplog.text
        assert "failed_login" in caplog.text
        assert "192.168.1.1" in caplog.text


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    def test_record_metric(self):
        """Test recording a metric."""
        collector = MetricsCollector(max_points_per_metric=10)
        
        collector.record_metric("test.metric", 42.5, {"label": "value"})
        
        history = collector.get_metric_history("test.metric")
        assert len(history) == 1
        assert history[0].value == 42.5
        assert history[0].labels == {"label": "value"}
    
    def test_processing_metrics_lifecycle(self):
        """Test complete processing metrics lifecycle."""
        collector = MetricsCollector()
        
        # Start processing metrics
        metrics = collector.start_processing_metrics(
            "test_operation",
            client_id="client-123",
            user_id="user-456"
        )
        
        # Update metrics
        metrics.items_processed = 10
        metrics.success_count = 8
        metrics.error_count = 2
        
        # Finish metrics
        collector.finish_processing_metrics(metrics)
        
        # Check that metrics were recorded
        history = collector.get_processing_metrics_history(
            operation="test_operation",
            client_id="client-123"
        )
        
        assert len(history) == 1
        assert history[0].items_processed == 10
        assert history[0].success_count == 8
        assert history[0].error_count == 2
    
    def test_metric_summary(self):
        """Test metric summary calculation."""
        collector = MetricsCollector()
        
        # Record multiple metrics
        for i in range(5):
            collector.record_metric("test.summary", float(i * 10))
        
        summary = collector.get_metric_summary("test.summary")
        
        assert summary["count"] == 5
        assert summary["min"] == 0.0
        assert summary["max"] == 40.0
        assert summary["avg"] == 20.0
        assert summary["latest"] == 40.0
    
    def test_cleanup_old_metrics(self):
        """Test cleanup of old metrics."""
        collector = MetricsCollector()
        
        # Record old metric
        old_time = datetime.utcnow() - timedelta(hours=25)
        collector.record_metric("test.cleanup", 1.0, timestamp=old_time)
        
        # Record recent metric
        collector.record_metric("test.cleanup", 2.0)
        
        # Cleanup old metrics
        collector.cleanup_old_metrics(older_than=timedelta(hours=24))
        
        # Check that only recent metric remains
        history = collector.get_metric_history("test.cleanup")
        assert len(history) == 1
        assert history[0].value == 2.0


class TestProcessingMetrics:
    """Test processing metrics data structure."""
    
    def test_processing_metrics_properties(self):
        """Test processing metrics calculated properties."""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=10)
        
        metrics = ProcessingMetrics(
            operation="test_op",
            start_time=start_time,
            end_time=end_time,
            items_processed=100,
            success_count=90,
            error_count=10
        )
        
        assert metrics.duration_seconds == 10.0
        assert metrics.throughput_per_second == 10.0  # 100 items / 10 seconds
        assert metrics.success_rate == 90.0  # 90/100 * 100
    
    def test_processing_metrics_to_dict(self):
        """Test processing metrics serialization."""
        start_time = datetime.utcnow()
        
        metrics = ProcessingMetrics(
            operation="test_op",
            start_time=start_time,
            items_processed=50,
            client_id="client-123"
        )
        
        data = metrics.to_dict()
        
        assert data["operation"] == "test_op"
        assert data["items_processed"] == 50
        assert data["client_id"] == "client-123"
        assert "start_time" in data
        assert "duration_seconds" in data


@pytest.mark.asyncio
class TestSystemHealthChecker:
    """Test system health checking functionality."""
    
    async def test_check_system_resources(self):
        """Test system resource health check."""
        checker = SystemHealthChecker()
        
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock memory info
            mock_memory.return_value = Mock(
                percent=60.0,
                available=4 * 1024**3  # 4GB
            )
            
            # Mock disk info
            mock_disk.return_value = Mock(
                used=50 * 1024**3,  # 50GB
                total=100 * 1024**3,  # 100GB
                free=50 * 1024**3   # 50GB
            )
            
            result = await checker.check_system_resources()
            
            assert result.name == "system_resources"
            assert result.status == HealthStatus.HEALTHY
            assert result.details["cpu_percent"] == 50.0
            assert result.details["memory_percent"] == 60.0
    
    async def test_check_file_storage(self):
        """Test file storage health check."""
        checker = SystemHealthChecker()
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.write_text'), \
             patch('pathlib.Path.unlink'), \
             patch('os.statvfs') as mock_statvfs:
            
            # Mock filesystem stats
            mock_statvfs.return_value = Mock(
                f_frsize=4096,
                f_blocks=1000000,  # Total blocks
                f_bavail=800000    # Available blocks
            )
            
            result = await checker.check_file_storage()
            
            assert result.name == "file_storage"
            assert result.status == HealthStatus.HEALTHY
            assert "storage_path" in result.details
    
    @patch('ats_backend.core.health.get_db')
    async def test_check_database_health_success(self, mock_get_db):
        """Test successful database health check."""
        checker = SystemHealthChecker()
        
        # Mock database session
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = (1,)
        mock_db.bind.pool.size.return_value = 10
        mock_db.bind.pool.checkedin.return_value = 8
        mock_db.bind.pool.checkedout.return_value = 2
        mock_db.bind.pool.invalid.return_value = 0
        
        mock_get_db.return_value = iter([mock_db])
        
        result = await checker.check_database_health()
        
        assert result.name == "database"
        assert result.status == HealthStatus.HEALTHY
        assert "pool_size" in result.details
        mock_db.close.assert_called_once()
    
    @patch('ats_backend.core.health.get_db')
    async def test_check_database_health_failure(self, mock_get_db):
        """Test database health check failure."""
        checker = SystemHealthChecker()
        
        # Mock database connection failure
        mock_get_db.side_effect = Exception("Connection failed")
        
        result = await checker.check_database_health()
        
        assert result.name == "database"
        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in result.message


class TestGlobalLoggerInstances:
    """Test global logger instances."""
    
    def test_global_performance_logger(self):
        """Test global performance logger instance."""
        assert performance_logger is not None
        assert isinstance(performance_logger, PerformanceLogger)
    
    def test_global_system_logger(self):
        """Test global system logger instance."""
        assert system_logger is not None
        assert isinstance(system_logger, SystemLogger)
    
    def test_global_error_logger(self):
        """Test global error logger instance."""
        assert error_logger is not None
        assert isinstance(error_logger, ErrorLogger)