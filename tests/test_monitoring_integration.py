"""Integration tests for monitoring endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime

from ats_backend.main import app
from ats_backend.auth.models import User
from ats_backend.core.health import HealthStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user for authentication."""
    user = Mock(spec=User)
    user.id = "user-123"
    user.client_id = "client-456"
    user.email = "test@example.com"
    return user


class TestMonitoringEndpoints:
    """Test monitoring API endpoints."""
    
    @patch('ats_backend.api.monitoring.get_current_user')
    @patch('ats_backend.core.health.health_checker.run_all_checks')
    def test_comprehensive_health_check(self, mock_health_check, mock_get_user, client, mock_current_user):
        """Test comprehensive health check endpoint."""
        mock_get_user.return_value = mock_current_user
        
        # Mock health check response
        mock_health_check.return_value = {
            "overall_status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "total_check_time_ms": 150.5,
            "checks": [
                {
                    "name": "database",
                    "status": "healthy",
                    "message": "Database connection successful",
                    "details": {"pool_size": 10},
                    "response_time_ms": 50.0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ],
            "summary": {
                "healthy_checks": 1,
                "degraded_checks": 0,
                "unhealthy_checks": 0,
                "unknown_checks": 0,
                "total_checks": 1
            }
        }
        
        response = client.get("/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "healthy"
        assert data["summary"]["total_checks"] == 1
        assert len(data["checks"]) == 1
    
    def test_simple_health_check(self, client):
        """Test simple health check endpoint (no auth required)."""
        response = client.get("/monitoring/health/simple")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ats-backend"
        assert "timestamp" in data
    
    @patch('ats_backend.api.monitoring.get_current_user')
    @patch('ats_backend.core.metrics.metrics_collector.get_comprehensive_metrics')
    def test_get_system_metrics(self, mock_get_metrics, mock_get_user, client, mock_current_user):
        """Test system metrics endpoint."""
        mock_get_user.return_value = mock_current_user
        
        # Mock metrics response
        mock_get_metrics.return_value = {
            "timestamp": datetime.utcnow().isoformat(),
            "queue_metrics": {
                "queues": {"email_processing": 5, "resume_processing": 3},
                "total_queued": 8
            },
            "worker_metrics": {
                "worker_stats": {"total_workers": 2},
                "active_tasks": {"total_active": 1}
            },
            "processing_summaries": {
                "email_processing": {
                    "count": 10,
                    "avg_duration": 2.5,
                    "avg_throughput": 4.0,
                    "avg_success_rate": 95.0
                }
            },
            "metric_counts": {"http.request.duration": 100},
            "total_processing_metrics": 10
        }
        
        response = client.get("/monitoring/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "queue_metrics" in data
        assert "worker_metrics" in data
        assert data["queue_metrics"]["total_queued"] == 8
    
    @patch('ats_backend.api.monitoring.get_current_user')
    @patch('ats_backend.core.metrics.metrics_collector.get_processing_metrics_history')
    def test_get_processing_metrics(self, mock_get_history, mock_get_user, client, mock_current_user):
        """Test processing metrics endpoint."""
        mock_get_user.return_value = mock_current_user
        
        # Mock processing metrics
        mock_metrics = Mock()
        mock_metrics.to_dict.return_value = {
            "operation": "email_processing",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "duration_seconds": 2.5,
            "items_processed": 10,
            "success_count": 9,
            "error_count": 1,
            "success_rate": 90.0,
            "throughput_per_second": 4.0,
            "client_id": "client-456"
        }
        
        mock_get_history.return_value = [mock_metrics]
        
        response = client.get("/monitoring/metrics/processing?operation=email_processing")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["operation"] == "email_processing"
        assert data["filters"]["operation"] == "email_processing"
    
    @patch('ats_backend.api.monitoring.get_current_user')
    @patch('ats_backend.core.metrics.metrics_collector.get_metric_summary')
    def test_get_metric_summary(self, mock_get_summary, mock_get_user, client, mock_current_user):
        """Test metric summary endpoint."""
        mock_get_user.return_value = mock_current_user
        
        # Mock metric summary
        mock_get_summary.return_value = {
            "name": "http.request.duration",
            "count": 100,
            "min": 0.1,
            "max": 5.0,
            "avg": 1.2,
            "latest": 0.8,
            "latest_timestamp": datetime.utcnow().isoformat()
        }
        
        response = client.get("/monitoring/metrics/summary/http.request.duration")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "http.request.duration"
        assert data["count"] == 100
        assert data["avg"] == 1.2
    
    @patch('ats_backend.api.monitoring.get_current_user')
    @patch('ats_backend.core.metrics.metrics_collector.cleanup_old_metrics')
    def test_cleanup_old_metrics(self, mock_cleanup, mock_get_user, client, mock_current_user):
        """Test metrics cleanup endpoint."""
        mock_get_user.return_value = mock_current_user
        
        response = client.post("/monitoring/metrics/cleanup?hours_old=48")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["hours_old"] == 48
        assert "Cleaned up metrics older than 48 hours" in data["message"]
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once()


class TestHealthCheckIntegration:
    """Test health check system integration."""
    
    def test_health_check_status_enum(self):
        """Test health status enumeration."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNKNOWN == "unknown"
    
    @patch('ats_backend.core.health.get_db')
    def test_database_health_check_integration(self, mock_get_db):
        """Test database health check integration."""
        from ats_backend.core.health import SystemHealthChecker
        
        # Mock successful database connection
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = (1,)
        mock_db.bind.pool.size.return_value = 10
        mock_db.bind.pool.checkedin.return_value = 8
        mock_db.bind.pool.checkedout.return_value = 2
        mock_db.bind.pool.invalid.return_value = 0
        
        mock_get_db.return_value = iter([mock_db])
        
        checker = SystemHealthChecker()
        
        # This would be async in real usage, but we're testing the mock setup
        import asyncio
        result = asyncio.run(checker.check_database_health())
        
        assert result.name == "database"
        assert result.status == HealthStatus.HEALTHY
        assert "Database connection successful" in result.message
        assert result.details["pool_size"] == 10
        mock_db.close.assert_called_once()


class TestLoggingIntegration:
    """Test logging system integration."""
    
    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        from ats_backend.core.logging import get_logger
        
        logger = get_logger("test_logger")
        assert logger is not None
        
        # Test that we can log without errors
        logger.info("Test log message", test_param="value")
    
    def test_performance_logger_integration(self):
        """Test performance logger integration."""
        from ats_backend.core.logging import performance_logger
        
        # Test that performance logger works
        with performance_logger.log_operation_time("test_operation"):
            pass  # Simulate work
        
        # If we get here without exceptions, the integration works
        assert True
    
    def test_metrics_collector_integration(self):
        """Test metrics collector integration."""
        from ats_backend.core.metrics import metrics_collector
        
        # Test recording a metric
        metrics_collector.record_metric("test.integration", 42.0)
        
        # Test retrieving metrics
        history = metrics_collector.get_metric_history("test.integration")
        assert len(history) >= 1
        assert history[-1].value == 42.0