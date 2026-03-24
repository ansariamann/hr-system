"""Audited base repository with automatic audit logging."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar, Type, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect
import structlog

from ats_backend.core.base import Base
from ats_backend.core.audit import AuditLogger
from .base import BaseRepository

logger = structlog.get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class AuditedRepository(BaseRepository[ModelType]):
    """Base repository with automatic audit logging."""
    
    def __init__(self, model: Type[ModelType]):
        """Initialize audited repository with model class.
        
        Args:
            model: SQLAlchemy model class
        """
        super().__init__(model)
        self.audit_logger = AuditLogger()
    
    def _make_json_safe(self, value: Any) -> Any:
        """Convert nested model values into JSON-serializable primitives."""
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): self._make_json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self._make_json_safe(item) for item in value]
        return value

    def _model_to_dict(self, instance: ModelType) -> Dict[str, Any]:
        """Convert model instance to dictionary for audit logging.
        
        Args:
            instance: Model instance
            
        Returns:
            Dictionary representation of the model
        """
        result = {}
        for column in inspect(instance).mapper.column_attrs:
            value = getattr(instance, column.key)
            result[column.key] = self._make_json_safe(value)
        return result
    
    def create_with_audit(
        self, 
        db: Session, 
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs
    ) -> ModelType:
        """Create a new record with audit logging.
        
        Args:
            db: Database session
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            **kwargs: Model field values
            
        Returns:
            Created model instance
        """
        # Ensure client_id is set for multi-tenant models
        if hasattr(self.model, 'client_id') and 'client_id' not in kwargs:
            kwargs['client_id'] = client_id
        
        instance = self.create(db, **kwargs)
        
        # Create audit log
        new_values = self._model_to_dict(instance)
        self.audit_logger.log_create(
            db=db,
            client_id=client_id,
            table_name=self.model.__tablename__,
            record_id=instance.id,
            new_values=new_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return instance
    
    def update_with_audit(
        self, 
        db: Session, 
        id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs
    ) -> Optional[ModelType]:
        """Update record by ID with audit logging.
        
        Args:
            db: Database session
            id: Record UUID
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            **kwargs: Fields to update
            
        Returns:
            Updated model instance if found, None otherwise
        """
        # Get old values before update
        instance = self.get_by_id(db, id)
        if not instance:
            return None
        
        old_values = self._model_to_dict(instance)
        
        # Perform update
        updated_instance = self.update(db, id, **kwargs)
        if not updated_instance:
            return None
        
        # Create audit log
        new_values = self._model_to_dict(updated_instance)
        self.audit_logger.log_update(
            db=db,
            client_id=client_id,
            table_name=self.model.__tablename__,
            record_id=id,
            old_values=old_values,
            new_values=new_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return updated_instance
    
    def delete_with_audit(
        self, 
        db: Session, 
        id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Delete record by ID with audit logging.
        
        Args:
            db: Database session
            id: Record UUID
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if deleted, False if not found
        """
        # Get old values before deletion
        instance = self.get_by_id(db, id)
        if not instance:
            return False
        
        old_values = self._model_to_dict(instance)
        
        # Perform deletion
        deleted = self.delete(db, id)
        if not deleted:
            return False
        
        # Create audit log
        self.audit_logger.log_delete(
            db=db,
            client_id=client_id,
            table_name=self.model.__tablename__,
            record_id=id,
            old_values=old_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True
    
    def soft_delete_with_audit(
        self, 
        db: Session, 
        id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Soft delete record by ID with audit logging.
        
        Args:
            db: Database session
            id: Record UUID
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if soft deleted, False if not found
        """
        # Get old values before soft deletion
        instance = self.get_by_id(db, id)
        if not instance:
            return False
        
        old_values = self._model_to_dict(instance)
        
        # Perform soft deletion (this method should be implemented by subclasses)
        if hasattr(self, 'soft_delete'):
            deleted = self.soft_delete(db, id)
        else:
            logger.warning(
                "Soft delete not implemented for model",
                model=self.model.__name__
            )
            return False
        
        if not deleted:
            return False
        
        # Create audit log
        self.audit_logger.log_soft_delete(
            db=db,
            client_id=client_id,
            table_name=self.model.__tablename__,
            record_id=id,
            old_values=old_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True
    
    def restore_with_audit(
        self, 
        db: Session, 
        id: UUID,
        client_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Restore soft-deleted record by ID with audit logging.
        
        Args:
            db: Database session
            id: Record UUID
            client_id: Client UUID for audit logging
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            True if restored, False if not found
        """
        # Perform restore (this method should be implemented by subclasses)
        if hasattr(self, 'restore'):
            restored = self.restore(db, id)
        else:
            logger.warning(
                "Restore not implemented for model",
                model=self.model.__name__
            )
            return False
        
        if not restored:
            return False
        
        # Get new values after restore
        instance = self.get_by_id(db, id)
        if not instance:
            return False
        
        new_values = self._model_to_dict(instance)
        
        # Create audit log
        self.audit_logger.log_restore(
            db=db,
            client_id=client_id,
            table_name=self.model.__tablename__,
            record_id=id,
            new_values=new_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True
