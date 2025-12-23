"""Audit logging system for tracking data modifications."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Session
import structlog

from .base import Base

logger = structlog.get_logger(__name__)


class AuditAction(str, Enum):
    """Audit action types."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SOFT_DELETE = "SOFT_DELETE"
    RESTORE = "RESTORE"


class AuditLog(Base):
    """Audit log model for tracking data modifications."""
    
    __tablename__ = "audit_logs"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(PG_UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), nullable=True)  # May be null for system actions
    table_name = Column(String(255), nullable=False)
    record_id = Column(PG_UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    changes = Column(JSONB, nullable=True)  # Specific fields that changed
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', table='{self.table_name}')>"


class AuditLogger:
    """Service for creating audit log entries."""
    
    @staticmethod
    def log_create(
        db: Session,
        client_id: UUID,
        table_name: str,
        record_id: UUID,
        new_values: Dict[str, Any],
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log a CREATE operation.
        
        Args:
            db: Database session
            client_id: Client UUID
            table_name: Name of the table
            record_id: ID of the created record
            new_values: New record values
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created audit log entry
        """
        audit_log = AuditLog(
            client_id=client_id,
            user_id=user_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.CREATE,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(
            "Audit log created for CREATE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return audit_log
    
    @staticmethod
    def log_update(
        db: Session,
        client_id: UUID,
        table_name: str,
        record_id: UUID,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log an UPDATE operation.
        
        Args:
            db: Database session
            client_id: Client UUID
            table_name: Name of the table
            record_id: ID of the updated record
            old_values: Previous record values
            new_values: New record values
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created audit log entry
        """
        # Calculate specific changes
        changes = {}
        for key, new_value in new_values.items():
            old_value = old_values.get(key)
            if old_value != new_value:
                changes[key] = {
                    "old": old_value,
                    "new": new_value
                }
        
        audit_log = AuditLog(
            client_id=client_id,
            user_id=user_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.UPDATE,
            old_values=old_values,
            new_values=new_values,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(
            "Audit log created for UPDATE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            changes_count=len(changes),
            user_id=str(user_id) if user_id else None
        )
        
        return audit_log
    
    @staticmethod
    def log_delete(
        db: Session,
        client_id: UUID,
        table_name: str,
        record_id: UUID,
        old_values: Dict[str, Any],
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log a DELETE operation.
        
        Args:
            db: Database session
            client_id: Client UUID
            table_name: Name of the table
            record_id: ID of the deleted record
            old_values: Previous record values
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created audit log entry
        """
        audit_log = AuditLog(
            client_id=client_id,
            user_id=user_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.DELETE,
            old_values=old_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(
            "Audit log created for DELETE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return audit_log
    
    @staticmethod
    def log_soft_delete(
        db: Session,
        client_id: UUID,
        table_name: str,
        record_id: UUID,
        old_values: Dict[str, Any],
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log a SOFT_DELETE operation.
        
        Args:
            db: Database session
            client_id: Client UUID
            table_name: Name of the table
            record_id: ID of the soft deleted record
            old_values: Previous record values
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created audit log entry
        """
        audit_log = AuditLog(
            client_id=client_id,
            user_id=user_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.SOFT_DELETE,
            old_values=old_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(
            "Audit log created for SOFT_DELETE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return audit_log
    
    @staticmethod
    def log_restore(
        db: Session,
        client_id: UUID,
        table_name: str,
        record_id: UUID,
        new_values: Dict[str, Any],
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log a RESTORE operation.
        
        Args:
            db: Database session
            client_id: Client UUID
            table_name: Name of the table
            record_id: ID of the restored record
            new_values: New record values after restore
            user_id: User who performed the action (optional)
            ip_address: IP address of the request (optional)
            user_agent: User agent of the request (optional)
            
        Returns:
            Created audit log entry
        """
        audit_log = AuditLog(
            client_id=client_id,
            user_id=user_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.RESTORE,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(
            "Audit log created for RESTORE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return audit_log
    
    @staticmethod
    def get_audit_trail(
        db: Session,
        client_id: UUID,
        table_name: Optional[str] = None,
        record_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[AuditLog]:
        """Get audit trail with optional filtering.
        
        Args:
            db: Database session
            client_id: Client UUID
            table_name: Filter by table name (optional)
            record_id: Filter by record ID (optional)
            user_id: Filter by user ID (optional)
            skip: Number of records to skip
            limit: Maximum number of records
            
        Returns:
            List of audit log entries
        """
        query = db.query(AuditLog).filter(AuditLog.client_id == client_id)
        
        if table_name:
            query = query.filter(AuditLog.table_name == table_name)
        
        if record_id:
            query = query.filter(AuditLog.record_id == record_id)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        return (
            query
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )