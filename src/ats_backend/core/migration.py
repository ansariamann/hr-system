"""Database migration utilities."""

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
import structlog

logger = structlog.get_logger(__name__)


class MigrationManager:
    """Manages database migrations using Alembic."""
    
    def __init__(self, alembic_cfg_path: str = "alembic.ini") -> None:
        """Initialize migration manager.
        
        Args:
            alembic_cfg_path: Path to alembic.ini configuration file
        """
        self.alembic_cfg_path = alembic_cfg_path
        self.config = None
    
    def _get_alembic_config(self) -> Config:
        """Get Alembic configuration.
        
        Returns:
            Alembic configuration object
            
        Raises:
            FileNotFoundError: If alembic.ini is not found
        """
        if self.config is None:
            if not os.path.exists(self.alembic_cfg_path):
                raise FileNotFoundError(f"Alembic config file not found: {self.alembic_cfg_path}")
            
            self.config = Config(self.alembic_cfg_path)
            
            # Set the script location relative to the project root
            script_location = self.config.get_main_option("script_location")
            if script_location:
                project_root = Path(__file__).parent.parent.parent.parent
                full_script_path = project_root / script_location
                self.config.set_main_option("script_location", str(full_script_path))
        
        return self.config
    
    def run_migrations(self) -> None:
        """Run all pending migrations to upgrade database to latest version."""
        try:
            config = self._get_alembic_config()
            command.upgrade(config, "head")
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error("Failed to run database migrations", error=str(e))
            raise
    
    def create_migration(self, message: str, autogenerate: bool = True) -> None:
        """Create a new migration.
        
        Args:
            message: Migration message/description
            autogenerate: Whether to auto-generate migration from model changes
        """
        try:
            config = self._get_alembic_config()
            if autogenerate:
                command.revision(config, message=message, autogenerate=True)
            else:
                command.revision(config, message=message)
            logger.info("Migration created", message=message)
        except Exception as e:
            logger.error("Failed to create migration", message=message, error=str(e))
            raise
    
    def get_current_revision(self) -> str:
        """Get current database revision.
        
        Returns:
            Current revision ID
        """
        try:
            config = self._get_alembic_config()
            # This would require a database connection to get the actual current revision
            # For now, return a placeholder
            return "unknown"
        except Exception as e:
            logger.error("Failed to get current revision", error=str(e))
            return "error"
    
    def downgrade(self, revision: str = "-1") -> None:
        """Downgrade database to specified revision.
        
        Args:
            revision: Target revision (default: previous revision)
        """
        try:
            config = self._get_alembic_config()
            command.downgrade(config, revision)
            logger.info("Database downgraded", revision=revision)
        except Exception as e:
            logger.error("Failed to downgrade database", revision=revision, error=str(e))
            raise


# Global migration manager instance
migration_manager = MigrationManager()


def run_migrations() -> None:
    """Run all pending database migrations."""
    migration_manager.run_migrations()


def create_migration(message: str, autogenerate: bool = True) -> None:
    """Create a new database migration."""
    migration_manager.create_migration(message, autogenerate)


def init_database() -> None:
    """Initialize database with migrations and setup."""
    from .database import db_manager
    
    logger.info("Initializing database...")
    
    # Initialize database connection
    db_manager.initialize()
    
    # Run migrations
    run_migrations()
    
    logger.info("Database initialization completed")