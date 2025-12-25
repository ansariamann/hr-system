"""Base classes and utilities for property-based testing."""

import asyncio
import pytest
from typing import Any, Dict, List, Optional
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock

from hypothesis import given, assume, note, event
from hypothesis.strategies import composite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ats_backend.core.database import get_db
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate
from ats_backend.models.application import Application
from ats_backend.models.resume_job import ResumeJob
from ats_backend.auth.models import User

from .config import PropertyTestConfig, get_test_seed
from .generators import (
    client_data, candidate_data, application_data, 
    resume_job_data, user_data, tenant_with_data
)


class PropertyTestBase:
    """Base class for property-based tests with common utilities."""
    
    def setup_method(self):
        """Setup method called before each test."""
        # Set deterministic seed if in CI
        seed = get_test_seed()
        if seed is not None:
            import random
            random.seed(seed)
    
    def assume_valid_data(self, data: Dict[str, Any], required_fields: List[str]):
        """Assume data contains all required fields with valid values."""
        for field in required_fields:
            assume(field in data)
            assume(data[field] is not None)
            if isinstance(data[field], str):
                assume(len(data[field].strip()) > 0)
    
    def log_test_data(self, description: str, data: Any):
        """Log test data for debugging purposes."""
        note(f"{description}: {data}")
        event(f"Testing {description}")
    
    def create_mock_db_session(self) -> MagicMock:
        """Create a mock database session for testing."""
        mock_session = MagicMock(spec=Session)
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.rollback = MagicMock()
        mock_session.close = MagicMock()
        mock_session.query = MagicMock()
        return mock_session
    
    def create_mock_async_db_session(self) -> AsyncMock:
        """Create a mock async database session for testing."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.execute = AsyncMock()
        return mock_session


class MultiTenantPropertyTest(PropertyTestBase):
    """Base class for multi-tenant property-based tests."""
    
    def verify_tenant_isolation(self, client_id: UUID, data_items: List[Any]):
        """Verify that all data items belong to the specified tenant."""
        for item in data_items:
            if hasattr(item, 'client_id'):
                assert item.client_id == client_id, f"Data item {item} does not belong to tenant {client_id}"
    
    def verify_no_cross_tenant_access(self, tenant1_id: UUID, tenant2_id: UUID, 
                                    tenant1_data: List[Any], tenant2_data: List[Any]):
        """Verify that tenant data is properly isolated."""
        # Ensure tenant1 data doesn't contain tenant2 IDs
        for item in tenant1_data:
            if hasattr(item, 'client_id'):
                assert item.client_id != tenant2_id, f"Tenant 1 data contains tenant 2 item: {item}"
        
        # Ensure tenant2 data doesn't contain tenant1 IDs
        for item in tenant2_data:
            if hasattr(item, 'client_id'):
                assert item.client_id != tenant1_id, f"Tenant 2 data contains tenant 1 item: {item}"


class SecurityPropertyTest(PropertyTestBase):
    """Base class for security-focused property-based tests."""
    
    def verify_no_sensitive_data_exposure(self, response_data: Dict[str, Any], 
                                        sensitive_fields: List[str]):
        """Verify that sensitive fields are not exposed in responses."""
        for field in sensitive_fields:
            assert field not in response_data, f"Sensitive field '{field}' found in response"
    
    def verify_authentication_required(self, operation_result: Any):
        """Verify that operations require proper authentication."""
        # This would be implemented based on specific authentication patterns
        pass
    
    def verify_authorization_enforced(self, user_client_id: UUID, 
                                    accessed_resource_client_id: UUID):
        """Verify that users can only access resources from their tenant."""
        assert user_client_id == accessed_resource_client_id, \
            f"User from tenant {user_client_id} accessed resource from tenant {accessed_resource_client_id}"


class FSMPropertyTest(PropertyTestBase):
    """Base class for Finite State Machine property-based tests."""
    
    VALID_CANDIDATE_STATES = ["ACTIVE", "INACTIVE", "JOINED", "LEFT_COMPANY"]
    VALID_APPLICATION_STATES = [
        "RECEIVED", "SCREENING", "INTERVIEW_SCHEDULED", "INTERVIEWED",
        "OFFER_EXTENDED", "OFFER_ACCEPTED", "OFFER_REJECTED", "REJECTED"
    ]
    VALID_RESUME_JOB_STATES = ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    
    def verify_valid_state(self, entity: Any, valid_states: List[str]):
        """Verify that entity is in a valid state."""
        if hasattr(entity, 'status'):
            assert entity.status in valid_states, \
                f"Entity {entity} has invalid status: {entity.status}"
    
    def verify_state_transition_valid(self, old_state: str, new_state: str, 
                                    valid_transitions: Dict[str, List[str]]):
        """Verify that state transition is valid."""
        if old_state in valid_transitions:
            assert new_state in valid_transitions[old_state], \
                f"Invalid transition from {old_state} to {new_state}"
    
    def verify_terminal_state_immutable(self, entity: Any, terminal_states: List[str]):
        """Verify that terminal states cannot be changed."""
        if hasattr(entity, 'status') and entity.status in terminal_states:
            # This would be verified by attempting state changes and ensuring they fail
            pass


class PerformancePropertyTest(PropertyTestBase):
    """Base class for performance-focused property-based tests."""
    
    def measure_operation_time(self, operation_func, *args, **kwargs):
        """Measure the time taken by an operation."""
        import time
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        
        note(f"Operation took {duration:.4f} seconds")
        return result, duration
    
    def verify_performance_threshold(self, duration: float, max_duration: float):
        """Verify that operation completed within performance threshold."""
        assert duration <= max_duration, \
            f"Operation took {duration:.4f}s, exceeding threshold of {max_duration}s"


# Utility decorators for property-based tests
def property_test(feature_name: str, property_number: int, property_description: str):
    """Decorator to mark and tag property-based tests."""
    def decorator(test_func):
        # Add metadata to the test function
        test_func._property_test_metadata = {
            "feature": feature_name,
            "property_number": property_number,
            "description": property_description,
            "tag": f"Feature: {feature_name}, Property {property_number}: {property_description}"
        }
        
        # Add pytest marker
        test_func = pytest.mark.property_test(test_func)
        
        return test_func
    return decorator


def requires_database(test_func):
    """Decorator to mark tests that require database access."""
    return pytest.mark.database(test_func)


def requires_redis(test_func):
    """Decorator to mark tests that require Redis access."""
    return pytest.mark.redis(test_func)


def slow_test(test_func):
    """Decorator to mark slow-running tests."""
    return pytest.mark.slow(test_func)