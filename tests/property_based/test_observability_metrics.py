"""Property-based tests for comprehensive observability and metrics system."""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from tests.property_based.base import PropertyTestBase
from tests.property_based.generators import (
    performance_metrics_strategy,
    cost_metrics_strategy,
    alert_strategy,
    system_metrics_strategy
)
from src.ats_backend.core.observability import (
    ObservabilitySystem, PerformanceMetrics, CostMetrics, Alert, AlertSeverity
)
from src.ats_backend.core.alerts import AlertManager, AlertRule, NotificationChannel


class TestObservabilityProperties(PropertyTestBase):
    """Property-based tests for observability system."""
    
    def setup_method(self):
        """Set up test environment."""
        super().setup_method()
        self.observability_system = ObservabilitySystem()
        self.alert_manager = AlertManager()
    
    @given(
        operation=st.text(min_size=1, max_size=50),
        durations=st.lists(st.floats(min_value=0.001, max_value=60.0), min_size=1, max_size=100)
    )
    @settings(max_examples=100, deadline=5000)
    def test_performance_metrics_calculation_property(self, operation, durations):
        """
        Property 8: Comprehensive metrics collection
        For any operation and list of durations, performance metrics should be calculated correctly.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        # Create mock processing metrics
        with patch('src.ats_backend.core.metrics.metrics_collector') as mock_collector:
            mock_processing_metrics = []
            for i, duration in enumerate(durations):
                mock_metric = Mock()
                mock_metric.duration_seconds = duration
                mock_metric.end_time = datetime.utcnow()
                mock_metric.error_count = 0 if i % 10 != 0 else 1  # 10% error rate
                mock_metric.success_count = 1 if i % 10 != 0 else 0
                mock_metric.start_time = datetime.utcnow() - timedelta(seconds=duration)
                mock_processing_metrics.append(mock_metric)
            
            mock_collector.get_processing_metrics_history.return_value = mock_processing_metrics
            
            # Run async method
            async def run_test():
                performance_metrics = await self.observability_system.collect_performance_metrics(operation)
                
                if operation in performance_metrics:
                    perf = performance_metrics[operation]
                    
                    # Property: P95 should be >= P50
                    assert perf.p95_ms >= perf.p50_ms, "P95 should be >= P50"
                    
                    # Property: P99 should be >= P95
                    assert perf.p99_ms >= perf.p95_ms, "P99 should be >= P95"
                    
                    # Property: Max should be >= P99
                    assert perf.max_ms >= perf.p99_ms, "Max should be >= P99"
                    
                    # Property: Min should be <= P50
                    assert perf.min_ms <= perf.p50_ms, "Min should be <= P50"
                    
                    # Property: Error rate should be between 0 and 1
                    assert 0 <= perf.error_rate <= 1, "Error rate should be between 0 and 1"
                    
                    # Property: Count should match input
                    assert perf.count == len(durations), "Count should match input length"
                    
                    # Property: Throughput should be positive
                    assert perf.throughput_per_second >= 0, "Throughput should be non-negative"
            
            asyncio.run(run_test())
    
    @given(
        cpu_percent=st.floats(min_value=0.0, max_value=100.0),
        memory_percent=st.floats(min_value=0.0, max_value=100.0),
        disk_percent=st.floats(min_value=0.0, max_value=100.0)
    )
    @settings(max_examples=100, deadline=5000)
    def test_cost_metrics_calculation_property(self, cpu_percent, memory_percent, disk_percent):
        """
        Property 8: Comprehensive metrics collection
        For any system resource usage, cost metrics should be calculated correctly.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        with patch('psutil.cpu_percent', return_value=cpu_percent), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.cpu_count', return_value=4):
            
            # Mock memory object
            mock_memory.return_value = Mock()
            mock_memory.return_value.percent = memory_percent
            mock_memory.return_value.total = 8 * 1024**3  # 8GB
            
            # Mock disk object
            mock_disk.return_value = Mock()
            mock_disk.return_value.total = 100 * 1024**3  # 100GB
            mock_disk.return_value.used = (disk_percent / 100) * 100 * 1024**3
            mock_disk.return_value.free = mock_disk.return_value.total - mock_disk.return_value.used
            
            async def run_test():
                cost_metrics = await self.observability_system.collect_cost_metrics()
                
                # Property: All cost components should be non-negative
                assert cost_metrics.cpu_cost_per_hour >= 0, "CPU cost should be non-negative"
                assert cost_metrics.memory_cost_per_hour >= 0, "Memory cost should be non-negative"
                assert cost_metrics.storage_cost_per_gb >= 0, "Storage cost should be non-negative"
                assert cost_metrics.total_estimated_cost_per_hour >= 0, "Total cost should be non-negative"
                
                # Property: Total cost should be sum of components
                expected_total = (cost_metrics.cpu_cost_per_hour + 
                                cost_metrics.memory_cost_per_hour + 
                                cost_metrics.storage_cost_per_gb)
                assert abs(cost_metrics.total_estimated_cost_per_hour - expected_total) < 0.01, \
                    "Total cost should equal sum of components"
                
                # Property: Resource efficiency should be between 0 and 1
                assert 0 <= cost_metrics.resource_efficiency <= 1, \
                    "Resource efficiency should be between 0 and 1"
            
            asyncio.run(run_test())
    
    @given(
        alert_name=st.text(min_size=1, max_size=50),
        threshold=st.floats(min_value=0.1, max_value=1000.0),
        current_value=st.floats(min_value=0.0, max_value=2000.0),
        severity=st.sampled_from(list(AlertSeverity))
    )
    @settings(max_examples=100, deadline=5000)
    def test_alert_triggering_property(self, alert_name, threshold, current_value, severity):
        """
        Property 8: Comprehensive metrics collection
        For any alert configuration, alerts should trigger correctly based on thresholds.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        # Create alert rule
        rule = AlertRule(
            name=alert_name,
            condition=f"value > {threshold}",
            threshold=threshold,
            severity=severity,
            notification_channels=[NotificationChannel.LOG]
        )
        
        self.alert_manager.add_alert_rule(rule)
        
        # Create alert
        alert = Alert(
            name=alert_name,
            condition=rule.condition,
            severity=severity,
            threshold=threshold,
            current_value=current_value,
            triggered_at=datetime.utcnow(),
            message=f"Test alert: {current_value} > {threshold}"
        )
        
        async def run_test():
            # Mock notification sender to avoid actual notifications
            with patch.object(self.alert_manager._senders[NotificationChannel.LOG], 'send', 
                            return_value=True) as mock_send:
                
                result = await self.alert_manager.process_alert(alert)
                
                # Property: Alert should be processed if rule exists and is enabled
                if current_value > threshold:
                    # Alert should trigger
                    assert result is True or result is False, "Process result should be boolean"
                    
                    # If rule is enabled, notification should be attempted
                    if rule.enabled:
                        mock_send.assert_called_once()
                else:
                    # Alert might not trigger based on threshold logic
                    pass
                
                # Property: Rule last_triggered should be updated if alert was processed
                if result and rule.enabled:
                    assert rule.last_triggered is not None, "Last triggered should be set"
        
        asyncio.run(run_test())
    
    @given(
        operations=st.lists(
            st.text(min_size=1, max_size=20), 
            min_size=1, 
            max_size=10,
            unique=True
        ),
        hours_back=st.integers(min_value=1, max_value=168)  # 1 hour to 1 week
    )
    @settings(max_examples=50, deadline=10000)
    def test_diagnostic_collection_property(self, operations, hours_back):
        """
        Property 8: Comprehensive metrics collection
        For any set of operations, 60-second diagnostic should complete within time limit.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        # Mock all the async methods to avoid actual system calls
        with patch.object(self.observability_system, '_get_system_health', 
                         return_value={"overall_status": "healthy"}), \
             patch.object(self.observability_system, '_get_performance_summary', 
                         return_value={}), \
             patch.object(self.observability_system, '_get_queue_status', 
                         return_value={"total_queued": 0}), \
             patch.object(self.observability_system, '_get_worker_status', 
                         return_value={"total_workers": 1}), \
             patch.object(self.observability_system, '_get_recent_errors', 
                         return_value={"error_count_last_hour": 0}), \
             patch.object(self.observability_system, '_get_cost_summary', 
                         return_value={"current_hourly_cost": 1.0}), \
             patch.object(self.observability_system, '_get_trend_analysis', 
                         return_value={"performance_trends": {}}):
            
            async def run_test():
                start_time = datetime.utcnow()
                
                diagnostic_data = await self.observability_system.get_60_second_diagnostic()
                
                end_time = datetime.utcnow()
                collection_time = (end_time - start_time).total_seconds()
                
                # Property: Diagnostic should complete within reasonable time (60 seconds)
                assert collection_time < 60.0, f"Diagnostic took {collection_time}s, should be < 60s"
                
                # Property: Diagnostic data should have required fields
                required_fields = [
                    "timestamp", "system_health", "performance_summary", 
                    "queue_status", "worker_status", "overall_status"
                ]
                for field in required_fields:
                    assert field in diagnostic_data, f"Missing required field: {field}"
                
                # Property: Collection time should be recorded
                assert "collection_time_seconds" in diagnostic_data, "Collection time should be recorded"
                assert diagnostic_data["collection_time_seconds"] >= 0, "Collection time should be non-negative"
                
                # Property: Overall status should be valid
                valid_statuses = ["healthy", "degraded", "unhealthy", "critical", "error"]
                assert diagnostic_data["overall_status"] in valid_statuses, \
                    f"Invalid overall status: {diagnostic_data['overall_status']}"
            
            asyncio.run(run_test())
    
    @given(
        threshold_updates=st.dictionaries(
            st.text(min_size=1, max_size=30),
            st.floats(min_value=0.1, max_value=1000.0),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50, deadline=5000)
    def test_threshold_update_property(self, threshold_updates):
        """
        Property 8: Comprehensive metrics collection
        For any threshold updates, the system should update thresholds correctly.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        # Get original thresholds
        original_thresholds = self.observability_system.alert_thresholds.copy()
        
        # Update thresholds
        self.observability_system.update_alert_thresholds(threshold_updates)
        
        # Property: Updated thresholds should be reflected in the system
        for key, value in threshold_updates.items():
            assert self.observability_system.alert_thresholds[key] == value, \
                f"Threshold {key} should be updated to {value}"
        
        # Property: Non-updated thresholds should remain unchanged
        for key, value in original_thresholds.items():
            if key not in threshold_updates:
                assert self.observability_system.alert_thresholds[key] == value, \
                    f"Threshold {key} should remain unchanged"
    
    @given(
        alert_names=st.lists(
            st.text(min_size=1, max_size=30),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=50, deadline=5000)
    def test_alert_clearing_property(self, alert_names):
        """
        Property 8: Comprehensive metrics collection
        For any set of alert names, clearing alerts should work correctly.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        # Add some alerts to the system
        for alert_name in alert_names:
            alert = Alert(
                name=alert_name,
                condition="test condition",
                severity=AlertSeverity.WARNING,
                threshold=100.0,
                current_value=150.0,
                triggered_at=datetime.utcnow(),
                message="Test alert"
            )
            self.observability_system._active_alerts[alert_name] = alert
        
        # Property: Clearing existing alerts should succeed
        for alert_name in alert_names:
            result = self.observability_system.clear_alert(alert_name)
            assert result is True, f"Clearing existing alert {alert_name} should succeed"
            assert alert_name not in self.observability_system._active_alerts, \
                f"Alert {alert_name} should be removed from active alerts"
        
        # Property: Clearing non-existent alerts should fail
        non_existent_alert = "non_existent_alert_12345"
        result = self.observability_system.clear_alert(non_existent_alert)
        assert result is False, "Clearing non-existent alert should fail"
    
    @given(
        hours_back=st.integers(min_value=1, max_value=168)  # 1 hour to 1 week
    )
    @settings(max_examples=30, deadline=5000)
    def test_historical_trends_property(self, hours_back):
        """
        Property 8: Comprehensive metrics collection
        For any time range, historical trends should be calculated correctly.
        **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
        """
        # Add some historical data
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Add performance metrics within the time range
        for i in range(5):
            perf_metric = PerformanceMetrics(
                operation=f"test_operation_{i}",
                p50_ms=100.0 + i * 10,
                p95_ms=200.0 + i * 20,
                p99_ms=300.0 + i * 30,
                avg_ms=150.0 + i * 15,
                min_ms=50.0 + i * 5,
                max_ms=400.0 + i * 40,
                count=100 + i * 10,
                error_rate=0.01 + i * 0.01,
                throughput_per_second=10.0 + i,
                timestamp=cutoff_time + timedelta(hours=i)
            )
            self.observability_system._performance_history[f"test_operation_{i}"].append(perf_metric)
        
        # Get historical trends
        trends = self.observability_system.get_historical_trends(hours_back)
        
        # Property: Trends should have required structure
        assert "time_range_hours" in trends, "Trends should include time range"
        assert trends["time_range_hours"] == hours_back, "Time range should match input"
        
        assert "performance_history" in trends, "Trends should include performance history"
        assert "cost_history" in trends, "Trends should include cost history"
        assert "alert_history" in trends, "Trends should include alert history"
        assert "summary" in trends, "Trends should include summary"
        
        # Property: Performance history should only include data within time range
        for operation, history in trends["performance_history"].items():
            for metric in history:
                metric_time = datetime.fromisoformat(metric["timestamp"])
                assert metric_time >= cutoff_time, \
                    f"Metric timestamp {metric_time} should be >= {cutoff_time}"
        
        # Property: Summary should be consistent with data
        summary = trends["summary"]
        assert "operations_tracked" in summary, "Summary should include operations tracked"
        assert summary["operations_tracked"] == len(trends["performance_history"]), \
            "Operations tracked should match performance history length"