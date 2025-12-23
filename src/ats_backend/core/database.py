"""Database connection and session management with connection pooling."""

from contextlib import contextmanager
from typing import Generator, Optional
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .config import settings
from .base import Base
import structlog

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Manages database connections with connection pooling."""
    
    def __init__(self, database_url: str) -> None:
        """Initialize database manager with connection pooling.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
    
    def initialize(self) -> None:
        """Initialize database engine with connection pooling."""
        if self.engine is not None:
            logger.warning("Database engine already initialized")
            return
        
        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=10,  # Number of connections to maintain
            max_overflow=20,  # Additional connections when pool is full
            pool_timeout=30,  # Timeout for getting connection from pool
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Verify connections before using
            echo=settings.log_level == "DEBUG",
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info(
            "Database engine initialized",
            pool_size=10,
            max_overflow=20,
            database=settings.postgres_db
        )
    
    def close(self) -> None:
        """Close database engine and dispose of connection pool."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database engine closed")
            self.engine = None
            self.SessionLocal = None
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with automatic cleanup.
        
        Yields:
            Database session
            
        Raises:
            RuntimeError: If database is not initialized
        """
        if self.SessionLocal is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def set_client_context(self, session: Session, client_id: UUID) -> None:
        """Set client context for RLS policies.
        
        Args:
            session: Database session
            client_id: Client UUID for RLS context
        """
        from .session_context import set_client_context
        set_client_context(session, client_id)
    
    def create_tables(self) -> None:
        """Create all database tables."""
        if self.engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")
    
    def health_check(self) -> bool:
        """Check database connectivity.
        
        Returns:
            True if database is accessible, False otherwise
        """
        try:
            if self.engine is None:
                return False
            
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database manager instance
db_manager = DatabaseManager(settings.database_url)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session.
    
    Yields:
        Database session
    """
    with db_manager.get_session() as session:
        yield session


def init_db() -> None:
    """Initialize database connection and run migrations."""
    from .migration import init_database
    init_database()


def close_db() -> None:
    """Close database connections."""
    db_manager.close()