"""Base repository class with common CRUD operations."""

from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import structlog

from ats_backend.core.base import Base

logger = structlog.get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, model: Type[ModelType]):
        """Initialize repository with model class.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model
    
    def create(self, db: Session, **kwargs) -> ModelType:
        """Create a new record.
        
        Args:
            db: Database session
            **kwargs: Model field values
            
        Returns:
            Created model instance
            
        Raises:
            ValueError: If creation fails due to constraint violations
        """
        try:
            instance = self.model(**kwargs)
            db.add(instance)
            db.commit()
            db.refresh(instance)
            
            logger.info(
                "Record created",
                model=self.model.__name__,
                id=str(instance.id) if hasattr(instance, 'id') else None
            )
            return instance
            
        except IntegrityError as e:
            db.rollback()
            logger.error(
                "Record creation failed",
                model=self.model.__name__,
                error=str(e)
            )
            raise ValueError(f"Failed to create {self.model.__name__}: {str(e)}")
    
    def get_by_id(self, db: Session, id: UUID) -> Optional[ModelType]:
        """Get record by ID.
        
        Args:
            db: Database session
            id: Record UUID
            
        Returns:
            Model instance if found, None otherwise
        """
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple records with pagination and filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters to apply
            
        Returns:
            List of model instances
        """
        query = db.query(self.model)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def update(self, db: Session, id: UUID, **kwargs) -> Optional[ModelType]:
        """Update record by ID.
        
        Args:
            db: Database session
            id: Record UUID
            **kwargs: Fields to update
            
        Returns:
            Updated model instance if found, None otherwise
            
        Raises:
            ValueError: If update fails due to constraint violations
        """
        instance = self.get_by_id(db, id)
        if not instance:
            logger.warning(
                "Record not found for update",
                model=self.model.__name__,
                id=str(id)
            )
            return None
        
        try:
            for field, value in kwargs.items():
                if hasattr(instance, field) and value is not None:
                    setattr(instance, field, value)
            
            db.commit()
            db.refresh(instance)
            
            logger.info(
                "Record updated",
                model=self.model.__name__,
                id=str(id)
            )
            return instance
            
        except IntegrityError as e:
            db.rollback()
            logger.error(
                "Record update failed",
                model=self.model.__name__,
                id=str(id),
                error=str(e)
            )
            raise ValueError(f"Failed to update {self.model.__name__}: {str(e)}")
    
    def delete(self, db: Session, id: UUID) -> bool:
        """Delete record by ID.
        
        Args:
            db: Database session
            id: Record UUID
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValueError: If deletion fails
        """
        instance = self.get_by_id(db, id)
        if not instance:
            logger.warning(
                "Record not found for deletion",
                model=self.model.__name__,
                id=str(id)
            )
            return False
        
        try:
            db.delete(instance)
            db.commit()
            
            logger.info(
                "Record deleted",
                model=self.model.__name__,
                id=str(id)
            )
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(
                "Record deletion failed",
                model=self.model.__name__,
                id=str(id),
                error=str(e)
            )
            raise ValueError(f"Failed to delete {self.model.__name__}: {str(e)}")
    
    def count(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering.
        
        Args:
            db: Database session
            filters: Optional filters to apply
            
        Returns:
            Number of records matching criteria
        """
        query = db.query(self.model)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
        
        return query.count()
    
    def exists(self, db: Session, id: UUID) -> bool:
        """Check if record exists by ID.
        
        Args:
            db: Database session
            id: Record UUID
            
        Returns:
            True if record exists, False otherwise
        """
        return db.query(self.model).filter(self.model.id == id).first() is not None