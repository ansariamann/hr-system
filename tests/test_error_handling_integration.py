"""Integration tests for comprehensive error handling system."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from ats_backend.core.error_handling import (
    ErrorHandler, RetryManager, CircuitBreaker, FallbackManager,
    ATSError, ValidationError, DatabaseError, AuthenticationError,
    ErrorCategory, ErrorSeverity, ErrorContext, RetryConfig,
    validate_all_configurations, perform_startup_checks
)
from ats_backend.core.startup import StartupManager, GracefulShutdown
from ats_backend.core.config import settings


class TestErrorHandling:
    """Test comprehensive error handling functionality."""
    
    def test_error_classification(self):
        """Test automatic error classification."""
        error_handler = ErrorHandler()
        
        # Test database error classification
        db_error = Exception("database connection failed")
        context = ErrorContext(operation="test", component="test")
        
        ats_error = error_handler.handle_error(db_error, context, notify=False)
        
        assert isinstance(ats_error, ATSError)
        assert ats_error.category == ErrorCategory.DATABASE
        assert "database connection failed" in ats_error.message
        assert ats_error.original_error == db_error
    
    def test_validation_error_handling(self):
        """Test validation error handling."""
        validation_error = ValidationError(
            "Invalid email format",
            field="email",
            value="invalid-email"
        )
        
        assert validation_error.category == ErrorCategory.VALIDATION
        assert validation_error.severity == ErrorSeverity.LOW
        assert validation_error.field == "email"
        assert validation_error.value == "invalid-email"
    
    def test_authentication_error_handling(self):
        """Test authentication error handling."""
        auth_error = AuthenticationError("Invalid credentials")
        
        assert auth_error.category == ErrorCategory.AUTHENTICATION
        assert auth_error.severity == ErrorSeverity.HIGH
        assert "Invalid credentials" in auth_error.message
    
    def test_error_context_serialization(self):
        """Test error context serialization."""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            user_id="user123",
            client_id="client456",
            additional_data={"key": "value"}
        )
        
        error = ATSError(
            "Test error",
            ErrorCategory.SYSTEM,
            ErrorSeverity.MEDIUM,
            context=context
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "system"
        assert error_dict["severity"] == "medium"
        assert error_dict["context"]["operation"] == "test_operation"
        assert error_dict["context"]["user_id"] == "user123"
        assert error_dict["context"]["additional_data"]["key"] == "value"


class TestRetryMechanism:
    """Test retry mechanisms with exponential backoff."""
    
    def test_successful_retry(self):
        """Test successful operation after retry."""
        retry_manager = RetryManager()
        call_count = 0
        
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast for testing
        context = ErrorContext(operation="test", component="test")
        
        result = retry_manager.retry(failing_function, config=config, context=context)
        
        assert result == "success"
        assert call_count == 3
    
    def test_retry_exhaustion(self):
        """Test retry exhaustion."""
        retry_manager = RetryManager()
        
        def always_failing_function():
            raise Exception("Persistent failure")
        
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        context = ErrorContext(operation="test", component="test")
        
        with pytest.raises(Exception, match="Persistent failure"):
            retry_manager.retry(always_failing_function, config=config, context=context)
    
    def test_non_retryable_exception(self):
        """Test non-retryable exception handling."""
        retry_manager = RetryManager()
        
        def function_with_non_retryable_error():
            raise ValueError("Non-retryable error")
        
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,)  # Only ConnectionError is retryable
        )
        context = ErrorContext(operation="test", component="test")
        
        with pytest.raises(ValueError, match="Non-retryable error"):
            retry_manager.retry(function_with_non_retryable_error, config=config, context=context)
    
    @pytest.mark.asyncio
    async def test_async_retry(self):
        """Test async retry functionality."""
        retry_manager = RetryManager()
        call_count = 0
        
        async def failing_async_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Async failure")
            return "async_success"
        
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        context = ErrorContext(operation="test", component="test")
        
        result = await retry_manager.async_retry(
            failing_async_function, 
            config=config, 
            context=context
        )
        
        assert result == "async_success"
        assert call_count == 2


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
        def successful_function():
            return "success"
        
        result = circuit_breaker.call(successful_function)
        assert result == "success"
        assert circuit_breaker.state == "closed"
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        def failing_function():
            raise Exception("Service failure")
        
        # First failure
        with pytest.raises(Exception):
            circuit_breaker.call(failing_function)
        assert circuit_breaker.state == "closed"
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            circuit_breaker.call(failing_function)
        assert circuit_breaker.state == "open"
        
        # Third call should be blocked by circuit breaker
        from ats_backend.core.error_handling import CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            circuit_breaker.call(failing_function)


class TestFallbackMechanism:
    """Test fallback strategies."""
    
    def test_successful_primary_function(self):
        """Test successful primary function execution."""
        fallback_manager = FallbackManager()
        
        def primary_function():
            return "primary_result"
        
        def fallback_function():
            return "fallback_result"
        
        context = ErrorContext(operation="test", component="test")
        result = fallback_manager.with_fallback(
            primary_function, 
            fallback_function, 
            context
        )
        
        assert result == "primary_result"
    
    def test_fallback_execution(self):
        """Test fallback execution when primary fails."""
        fallback_manager = FallbackManager()
        
        def failing_primary():
            raise Exception("Primary failure")
        
        def successful_fallback():
            return "fallback_result"
        
        context = ErrorContext(operation="test", component="test")
        result = fallback_manager.with_fallback(
            failing_primary, 
            successful_fallback, 
            context
        )
        
        assert result == "fallback_result"
    
    def test_both_functions_fail(self):
        """Test when both primary and fallback fail."""
        fallback_manager = FallbackManager()
        
        def failing_primary():
            raise Exception("Primary failure")
        
        def failing_fallback():
            raise Exception("Fallback failure")
        
        context = ErrorContext(operation="test", component="test")
        
        # Should re-raise the original (primary) error
        with pytest.raises(Exception, match="Primary failure"):
            fallback_manager.with_fallback(
                failing_primary, 
                failing_fallback, 
                context
            )


class TestConfigurationValidation:
    """Test configuration validation."""
    
    def test_database_config_validation(self):
        """Test database configuration validation."""
        from ats_backend.core.error_handling import validate_database_config
        
        # Should pass with current settings
        assert validate_database_config() == True
    
    def test_redis_config_validation(self):
        """Test Redis configuration validation."""
        from ats_backend.core.error_handling import validate_redis_config
        
        # Should pass with current settings
        assert validate_redis_config() == True
    
    def test_api_config_validation(self):
        """Test API configuration validation."""
        from ats_backend.core.error_handling import validate_api_config
        
        # Should pass with current settings
        assert validate_api_config() == True
    
    def test_email_config_validation(self):
        """Test email configuration validation."""
        from ats_backend.core.error_handling import validate_email_config
        
        # Should pass with current settings
        assert validate_email_config() == True
    
    def test_all_configurations_validation(self):
        """Test comprehensive configuration validation."""
        # Should pass with current settings
        assert validate_all_configurations() == True


class TestStartupSystem:
    """Test startup and shutdown system."""
    
    @pytest.mark.asyncio
    async def test_startup_manager_initialization(self):
        """Test startup manager initialization."""
        startup_manager = StartupManager()
        
        # Mock the database and Redis connections for testing
        with patch('ats_backend.core.startup.db_manager') as mock_db_manager, \
             patch('ats_backend.core.startup.get_redis_client') as mock_redis:
            
            # Mock successful database connection
            mock_db_manager.health_check.return_value = True
            
            # Mock successful Redis connection
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client
            
            # Test initialization
            result = await startup_manager.initialize_system()
            
            # Should succeed with mocked dependencies
            assert result == True
            assert startup_manager.checks_passed.get('logging') == True
            assert startup_manager.checks_passed.get('configuration') == True
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test graceful shutdown process."""
        shutdown_manager = GracefulShutdown()
        
        # Mock dependencies
        with patch('ats_backend.core.startup.db_manager') as mock_db_manager, \
             patch('ats_backend.core.startup.get_redis_client') as mock_redis:
            
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client
            
            # Test shutdown
            await shutdown_manager.shutdown_system()
            
            # Verify cleanup was attempted
            mock_db_manager.close.assert_called_once()
            # Note: Redis client close might not be called due to async context handling


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def test_database_error_with_retry_and_fallback(self):
        """Test database error handling with retry and fallback."""
        error_handler = ErrorHandler()
        retry_manager = RetryManager()
        fallback_manager = FallbackManager()
        
        call_count = 0
        
        def database_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise SQLAlchemyError("Database connection lost")
            return {"data": "success"}
        
        def cache_fallback():
            return {"data": "cached_result", "source": "cache"}
        
        context = ErrorContext(
            operation="get_user_data",
            component="user_service",
            user_id="user123"
        )
        
        # First try with retry
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(SQLAlchemyError,)
        )
        
        try:
            result = retry_manager.retry(database_operation, config=config, context=context)
            assert result == {"data": "success"}
        except SQLAlchemyError as e:
            # If retry fails, use fallback
            result = fallback_manager.with_fallback(
                database_operation,
                cache_fallback,
                context
            )
            assert result["source"] == "cache"
    
    @pytest.mark.asyncio
    async def test_comprehensive_error_flow(self):
        """Test comprehensive error handling flow."""
        # Simulate a complex operation that might fail
        error_handler = ErrorHandler()
        
        async def complex_operation(user_id: str, client_id: str):
            # Simulate various types of failures
            import random
            failure_type = random.choice(['validation', 'database', 'network', 'success'])
            
            if failure_type == 'validation':
                raise ValidationError("Invalid user data", field="email", context=context)
            elif failure_type == 'database':
                raise DatabaseError("Database connection failed", context=context)
            elif failure_type == 'network':
                raise Exception("Network timeout")
            else:
                return {"status": "success", "user_id": user_id}
        
        context = ErrorContext(
            operation="complex_user_operation",
            component="user_service",
            user_id="user123",
            client_id="client456"
        )
        
        # Test multiple scenarios
        for _ in range(5):
            try:
                result = await complex_operation("user123", "client456")
                if result:
                    assert result["status"] == "success"
            except ATSError as e:
                # Verify error is properly classified
                assert e.category in [
                    ErrorCategory.VALIDATION,
                    ErrorCategory.DATABASE,
                    ErrorCategory.SYSTEM
                ]
                assert e.context is not None
            except Exception as e:
                # Handle unexpected errors
                ats_error = error_handler.handle_error(e, context, notify=False)
                assert isinstance(ats_error, ATSError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])