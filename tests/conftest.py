"""Pytest configuration for ATS backend tests."""

import os
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

# Configure Hypothesis before importing test modules
from tests.property_based.config import PropertyTestConfig
PropertyTestConfig.configure_hypothesis()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Provide a mock database session for testing."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.close = MagicMock()
    mock_session.query = MagicMock()
    return mock_session


@pytest.fixture
async def mock_async_db_session():
    """Provide a mock async database session for testing."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.execute = AsyncMock()
    return mock_session


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client for testing."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.exists = AsyncMock()
    mock_redis.incr = AsyncMock()
    mock_redis.publish = AsyncMock()
    mock_redis.subscribe = AsyncMock()
    return mock_redis


# Pytest markers for organizing tests
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "property_test: mark test as a property-based test"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database access"
    )
    config.addinivalue_line(
        "markers", "redis: mark test as requiring Redis access"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add property_test marker to tests in property_based directory
        if "property_based" in str(item.fspath):
            item.add_marker(pytest.mark.property_test)
        
        # Add integration marker to integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add unit marker to unit tests
        if "test_" in str(item.fspath) and "integration" not in str(item.fspath) and "property_based" not in str(item.fspath):
            item.add_marker(pytest.mark.unit)


def pytest_runtest_setup(item):
    """Setup for each test run."""
    # Set environment variables for testing
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically setup test environment for all tests."""
    # Ensure we're in test mode
    os.environ["TESTING"] = "1"
    yield
    # Cleanup after test
    pass


# Property-based test specific fixtures
@pytest.fixture
def property_test_config():
    """Provide property test configuration."""
    return PropertyTestConfig


@pytest.fixture
def hypothesis_seed():
    """Provide deterministic seed for property tests."""
    from tests.property_based.config import get_test_seed
    return get_test_seed()


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Provide a performance timer for tests."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# Utility functions for test data cleanup
def cleanup_test_data():
    """Clean up test data after tests."""
    # This would implement cleanup logic for test databases
    pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_after_tests():
    """Cleanup after all tests complete."""
    yield
    cleanup_test_data()