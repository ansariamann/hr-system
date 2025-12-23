"""Session context management for multi-tenant RLS policies."""

from contextlib import contextmanager
from typing import Generator, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

logger = structlog.get_logger(__name__)


class SessionContextManager:
    """Manages database session context for RLS policies."""
    
    @staticmethod
    def set_client_context(session: Session, client_id: UUID) -> None:
        """Set client context for RLS policies.
        
        Args:
            session: Database session
            client_id: Client UUID for RLS context
            
        Raises:
            ValueError: If client_id is None or invalid
        """
        if client_id is None:
            raise ValueError("Client ID cannot be None")
        
        try:
            session.execute(
                text("SET LOCAL app.current_client_id = :client_id"),
                {"client_id": str(client_id)}
            )
            logger.debug("Client context set", client_id=str(client_id))
        except Exception as e:
            logger.error("Failed to set client context", client_id=str(client_id), error=str(e))
            raise
    
    @staticmethod
    def clear_client_context(session: Session) -> None:
        """Clear client context from session.
        
        Args:
            session: Database session
        """
        try:
            session.execute(text("SET LOCAL app.current_client_id = ''"))
            logger.debug("Client context cleared")
        except Exception as e:
            logger.error("Failed to clear client context", error=str(e))
            raise
    
    @staticmethod
    def get_current_client_id(session: Session) -> Optional[UUID]:
        """Get current client ID from session context.
        
        Args:
            session: Database session
            
        Returns:
            Current client UUID or None if not set
        """
        try:
            result = session.execute(
                text("SELECT current_setting('app.current_client_id', true)")
            ).scalar()
            
            if result and result.strip():
                return UUID(result)
            return None
        except Exception as e:
            logger.error("Failed to get current client context", error=str(e))
            return None
    
    @staticmethod
    @contextmanager
    def with_client_context(
        session: Session, client_id: UUID
    ) -> Generator[Session, None, None]:
        """Context manager for temporary client context.
        
        Args:
            session: Database session
            client_id: Client UUID for RLS context
            
        Yields:
            Database session with client context set
        """
        original_client_id = SessionContextManager.get_current_client_id(session)
        
        try:
            SessionContextManager.set_client_context(session, client_id)
            yield session
        finally:
            if original_client_id:
                SessionContextManager.set_client_context(session, original_client_id)
            else:
                SessionContextManager.clear_client_context(session)


# Convenience functions for easier usage
def set_client_context(session: Session, client_id: UUID) -> None:
    """Set client context for RLS policies."""
    SessionContextManager.set_client_context(session, client_id)


def clear_client_context(session: Session) -> None:
    """Clear client context from session."""
    SessionContextManager.clear_client_context(session)


def get_current_client_id(session: Session) -> Optional[UUID]:
    """Get current client ID from session context."""
    return SessionContextManager.get_current_client_id(session)


@contextmanager
def with_client_context(
    session: Session, client_id: UUID
) -> Generator[Session, None, None]:
    """Context manager for temporary client context."""
    with SessionContextManager.with_client_context(session, client_id) as ctx_session:
        yield ctx_session