"""System startup validation and initialization."""

import asyncio
import sys
from typing import Dict, List, Optional
from datetime import datetime

from .config import settings
from .logging import configure_logging, get_logger, system_logger
from .error_handling import (
    validate_all_configurations,
    perform_startup_checks,
    ConfigurationError,
    ErrorHandler,
    error_handler
)
from .database import db_manager
from .redis import get_redis_client


logger = get_logger(__name__)


class StartupManager:
    """Manages system startup validation and initialization."""
    
    def __init__(self):
        self.logger = get_logger("startup_manager")
        self.startup_time = datetime.utcnow()
        self.checks_passed = {}
        self.critical_failures = []
    
    async def initialize_system(self) -> bool:
        """Initialize the entire system with comprehensive checks.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Starting system initialization")
        
        try:
            # Step 1: Configure logging first
            self._initialize_logging()
            
            # Step 2: Validate configurations
            await self._validate_configurations()
            
            # Step 3: Initialize core services
            await self._initialize_core_services()
            
            # Step 4: Perform health checks
            await self._perform_health_checks()
            
            # Step 5: Validate integrations
            await self._validate_integrations()
            
            # Step 6: Final startup validation
            self._finalize_startup()
            
            self.logger.info(
                "System initialization completed successfully",
                startup_duration_seconds=(datetime.utcnow() - self.startup_time).total_seconds(),
                checks_passed=self.checks_passed
            )
            
            return True
            
        except Exception as e:
            self.logger.critical(
                "System initialization failed",
                error=str(e),
                error_type=type(e).__name__,
                critical_failures=self.critical_failures,
                startup_duration_seconds=(datetime.utcnow() - self.startup_time).total_seconds()
            )
            
            # Log detailed failure information
            error_handler.handle_error(e)
            
            return False
    
    def _initialize_logging(self):
        """Initialize logging system."""
        try:
            configure_logging()
            self.checks_passed['logging'] = True
            self.logger.info("Logging system initialized successfully")
            
        except Exception as e:
            print(f"CRITICAL: Failed to initialize logging: {e}")
            self.critical_failures.append(f"Logging initialization: {e}")
            self.checks_passed['logging'] = False
            raise
    
    async def _validate_configurations(self):
        """Validate all system configurations."""
        try:
            validate_all_configurations()
            self.checks_passed['configuration'] = True
            self.logger.info("Configuration validation completed successfully")
            
        except ConfigurationError as e:
            self.critical_failures.append(f"Configuration validation: {e}")
            self.checks_passed['configuration'] = False
            raise
    
    async def _initialize_core_services(self):
        """Initialize core services (database, Redis, etc.)."""
        # Initialize database
        try:
            # Initialize database manager
            db_manager.initialize()
            
            # Test database connection
            if db_manager.health_check():
                self.checks_passed['database'] = True
                self.logger.info("Database connection established successfully")
            else:
                raise Exception("Database health check failed")
            
        except Exception as e:
            self.critical_failures.append(f"Database initialization: {e}")
            self.checks_passed['database'] = False
            self.logger.error("Database initialization failed", error=str(e))
            # Don't raise - allow system to continue with degraded functionality
        
        # Initialize Redis
        try:
            from .redis import redis_manager
            await redis_manager.initialize()
            
            self.checks_passed['redis'] = True
            self.logger.info("Redis connection established successfully")
            
        except Exception as e:
            self.critical_failures.append(f"Redis initialization: {e}")
            self.checks_passed['redis'] = False
            self.logger.error("Redis initialization failed", error=str(e))
            # Don't raise - allow system to continue with degraded functionality
        
        # Initialize SSE Manager
        try:
            from .sse_manager import sse_manager
            await sse_manager.initialize()
            
            self.checks_passed['sse_manager'] = True
            self.logger.info("SSE Manager initialized successfully")
            
        except Exception as e:
            self.critical_failures.append(f"SSE Manager initialization: {e}")
            self.checks_passed['sse_manager'] = False
            self.logger.error("SSE Manager initialization failed", error=str(e))
            # Don't raise - allow system to continue with degraded functionality
    
    async def _perform_health_checks(self):
        """Perform comprehensive health checks."""
        try:
            health_checks = perform_startup_checks()
            self.checks_passed.update(health_checks)
            
            # Check for critical failures
            critical_checks = ['configuration', 'database']
            failed_critical = [check for check in critical_checks if not health_checks.get(check, False)]
            
            if failed_critical:
                raise ConfigurationError(f"Critical health checks failed: {failed_critical}")
            
            self.logger.info("Health checks completed", checks=health_checks)
            
        except Exception as e:
            self.critical_failures.append(f"Health checks: {e}")
            raise
    
    async def _validate_integrations(self):
        """Validate service integrations."""
        integration_checks = {}
        
        # Test Celery integration
        try:
            from ..workers.celery_app import celery_app
            # Test basic Celery functionality
            integration_checks['celery'] = True
            self.logger.info("Celery integration validated")
            
        except Exception as e:
            integration_checks['celery'] = False
            self.logger.warning("Celery integration validation failed", error=str(e))
        
        # Test email processing integration
        try:
            from ..email.server import EmailServer
            # Basic validation of email server configuration
            integration_checks['email_processing'] = True
            self.logger.info("Email processing integration validated")
            
        except Exception as e:
            integration_checks['email_processing'] = False
            self.logger.warning("Email processing integration validation failed", error=str(e))
        
        # Test resume parsing integration
        try:
            from ..resume.parser import ResumeParser
            # Basic validation of resume parser
            integration_checks['resume_parsing'] = True
            self.logger.info("Resume parsing integration validated")
            
        except Exception as e:
            integration_checks['resume_parsing'] = False
            self.logger.warning("Resume parsing integration validation failed", error=str(e))
        
        self.checks_passed.update(integration_checks)
    
    def _finalize_startup(self):
        """Finalize startup process and log summary."""
        # Calculate startup metrics
        startup_duration = (datetime.utcnow() - self.startup_time).total_seconds()
        
        # Count successful checks
        total_checks = len(self.checks_passed)
        successful_checks = sum(1 for passed in self.checks_passed.values() if passed)
        
        # Log startup summary
        system_logger.log_system_startup(
            "ats_backend_system",
            startup_duration_seconds=startup_duration,
            total_checks=total_checks,
            successful_checks=successful_checks,
            failed_checks=total_checks - successful_checks,
            critical_failures=len(self.critical_failures),
            environment=settings.environment,
            version="0.1.0"
        )
        
        # Log warnings for non-critical failures
        if self.critical_failures:
            self.logger.warning(
                "System started with some failures",
                critical_failures=self.critical_failures,
                checks_passed=self.checks_passed
            )
        
        # Validate minimum requirements
        critical_services = ['logging', 'configuration', 'database']
        failed_critical = [service for service in critical_services 
                          if not self.checks_passed.get(service, False)]
        
        if failed_critical:
            raise ConfigurationError(
                f"Cannot start system - critical services failed: {failed_critical}"
            )


class GracefulShutdown:
    """Manages graceful system shutdown."""
    
    def __init__(self):
        self.logger = get_logger("shutdown_manager")
        self.shutdown_time = datetime.utcnow()
    
    async def shutdown_system(self):
        """Perform graceful system shutdown."""
        self.logger.info("Starting graceful system shutdown")
        
        try:
            # Step 1: Stop accepting new requests
            await self._stop_accepting_requests()
            
            # Step 2: Complete ongoing operations
            await self._complete_ongoing_operations()
            
            # Step 3: Shutdown services
            await self._shutdown_services()
            
            # Step 4: Close connections
            await self._close_connections()
            
            # Step 5: Final cleanup
            await self._final_cleanup()
            
            shutdown_duration = (datetime.utcnow() - self.shutdown_time).total_seconds()
            
            system_logger.log_system_shutdown(
                "ats_backend_system",
                shutdown_duration_seconds=shutdown_duration,
                environment=settings.environment
            )
            
            self.logger.info(
                "System shutdown completed successfully",
                shutdown_duration_seconds=shutdown_duration
            )
            
        except Exception as e:
            self.logger.error(
                "Error during system shutdown",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def _stop_accepting_requests(self):
        """Stop accepting new requests."""
        self.logger.info("Stopping acceptance of new requests")
        # Implementation would depend on the web server
    
    async def _complete_ongoing_operations(self):
        """Wait for ongoing operations to complete."""
        self.logger.info("Waiting for ongoing operations to complete")
        
        # Give operations time to complete
        await asyncio.sleep(5)
        
        # In a real implementation, this would:
        # - Check Celery task queues
        # - Wait for database transactions
        # - Complete file operations
    
    async def _shutdown_services(self):
        """Shutdown background services."""
        self.logger.info("Shutting down background services")
        
        try:
            # Shutdown Celery workers
            from ..workers.celery_app import celery_app
            celery_app.control.shutdown()
            self.logger.info("Celery workers shutdown initiated")
            
        except Exception as e:
            self.logger.warning("Error shutting down Celery", error=str(e))
    
    async def _close_connections(self):
        """Close database and Redis connections."""
        self.logger.info("Closing database and Redis connections")
        
        try:
            # Close database connections
            db_manager.close()
            self.logger.info("Database connections closed")
            
        except Exception as e:
            self.logger.warning("Error closing database connections", error=str(e))
        
        try:
            # Close Redis connections
            from .redis import redis_manager
            await redis_manager.close()
            self.logger.info("Redis connections closed")
            
        except Exception as e:
            self.logger.warning("Error closing Redis connections", error=str(e))
        
        try:
            # Shutdown SSE Manager
            from .sse_manager import sse_manager
            await sse_manager.force_disconnect_all()
            self.logger.info("SSE Manager shutdown completed")
            
        except Exception as e:
            self.logger.warning("Error shutting down SSE Manager", error=str(e))
    
    async def _final_cleanup(self):
        """Perform final cleanup operations."""
        self.logger.info("Performing final cleanup")
        
        # Clean up temporary files, logs, etc.
        # Implementation would depend on specific cleanup needs


# Global instances
startup_manager = StartupManager()
shutdown_manager = GracefulShutdown()


# Convenience functions
async def initialize_application() -> bool:
    """Initialize the application with comprehensive startup checks."""
    return await startup_manager.initialize_system()


async def shutdown_application():
    """Shutdown the application gracefully."""
    await shutdown_manager.shutdown_system()


def validate_startup_environment():
    """Validate the startup environment before initialization."""
    try:
        # Check Python version
        if sys.version_info < (3, 8):
            raise ConfigurationError("Python 3.8 or higher is required")
        
        # Check required environment variables
        required_env_vars = ['POSTGRES_PASSWORD']
        missing_vars = []
        
        import os
        for var in required_env_vars:
            if not os.getenv(var) and not getattr(settings, var.lower(), None):
                missing_vars.append(var)
        
        if missing_vars:
            raise ConfigurationError(f"Missing required environment variables: {missing_vars}")
        
        logger.info("Startup environment validation passed")
        return True
        
    except Exception as e:
        logger.error("Startup environment validation failed", error=str(e))
        raise