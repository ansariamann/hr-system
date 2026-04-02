"""Audit logging system for tracking data modifications."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from .base import Base
from ats_backend.core.custom_types import GUID
from ats_backend.models.activity_log import ActivityLog

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
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    user_id = Column(GUID(), nullable=True)  # May be null for system actions
    table_name = Column(String(255), nullable=False)
    record_id = Column(GUID(), nullable=False)
    action = Column(String(50), nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    changes = Column(JSON, nullable=True)  # Specific fields that changed
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', table='{self.table_name}')>"


class AuditLogger:
    """Service for creating audit log entries."""

    @staticmethod
    def _write_audit_log_safely(db: Session, audit_log: AuditLog) -> Optional[AuditLog]:
        """Write audit log using a savepoint so missing/invalid audit table does not break business flow."""
        try:
            with db.begin_nested():
                db.add(audit_log)
                db.flush()
            return audit_log
        except SQLAlchemyError as exc:
            logger.warning(
                "Audit log write skipped",
                error=str(exc),
                table_name=audit_log.table_name,
                record_id=str(audit_log.record_id),
                action=audit_log.action,
            )
            return None

    @staticmethod
    def _to_activity_action_type(table_name: str, action: AuditAction) -> str:
        entity = table_name.upper()
        if entity.endswith("IES"):
            entity = f"{entity[:-3]}Y"
        elif entity.endswith("S"):
            entity = entity[:-1]

        action_suffix = {
            AuditAction.CREATE: "CREATED",
            AuditAction.UPDATE: "UPDATED",
            AuditAction.DELETE: "DELETED",
            AuditAction.SOFT_DELETE: "SOFT_DELETED",
            AuditAction.RESTORE: "RESTORED",
        }[action]
        return f"{entity}_{action_suffix}"

    @staticmethod
    def _log_activity(
        db: Session,
        client_id: UUID,
        table_name: str,
        record_id: UUID,
        action: AuditAction,
        user_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActivityLog:
        activity_log = ActivityLog(
            client_id=client_id,
            user_id=user_id,
            action_type=AuditLogger._to_activity_action_type(table_name, action),
            entity_id=record_id,
            details=details or {},
        )
        db.add(activity_log)
        db.flush()
        return activity_log
    
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
    ) -> Optional[AuditLog]:
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
        
        saved_audit_log = AuditLogger._write_audit_log_safely(db, audit_log)
        AuditLogger._log_activity(
            db=db,
            client_id=client_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.CREATE,
            user_id=user_id,
            details={
                "table_name": table_name,
                "audit_action": AuditAction.CREATE.value,
                "new_values": new_values,
            },
        )
        
        logger.info(
            "Audit log created for CREATE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return saved_audit_log
    
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
    ) -> Optional[AuditLog]:
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
        
        saved_audit_log = AuditLogger._write_audit_log_safely(db, audit_log)
        AuditLogger._log_activity(
            db=db,
            client_id=client_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.UPDATE,
            user_id=user_id,
            details={
                "table_name": table_name,
                "audit_action": AuditAction.UPDATE.value,
                "change_count": len(changes),
                "changed_fields": sorted(changes.keys()),
                "changes": changes,
            },
        )
        
        logger.info(
            "Audit log created for UPDATE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            changes_count=len(changes),
            user_id=str(user_id) if user_id else None
        )
        
        return saved_audit_log
    
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
    ) -> Optional[AuditLog]:
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
        
        saved_audit_log = AuditLogger._write_audit_log_safely(db, audit_log)
        AuditLogger._log_activity(
            db=db,
            client_id=client_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.DELETE,
            user_id=user_id,
            details={
                "table_name": table_name,
                "audit_action": AuditAction.DELETE.value,
                "old_values": old_values,
            },
        )
        
        logger.info(
            "Audit log created for DELETE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return saved_audit_log
    
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
    ) -> Optional[AuditLog]:
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
        
        saved_audit_log = AuditLogger._write_audit_log_safely(db, audit_log)
        AuditLogger._log_activity(
            db=db,
            client_id=client_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.SOFT_DELETE,
            user_id=user_id,
            details={
                "table_name": table_name,
                "audit_action": AuditAction.SOFT_DELETE.value,
                "old_values": old_values,
            },
        )
        
        logger.info(
            "Audit log created for SOFT_DELETE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return saved_audit_log
    
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
    ) -> Optional[AuditLog]:
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
        
        saved_audit_log = AuditLogger._write_audit_log_safely(db, audit_log)
        AuditLogger._log_activity(
            db=db,
            client_id=client_id,
            table_name=table_name,
            record_id=record_id,
            action=AuditAction.RESTORE,
            user_id=user_id,
            details={
                "table_name": table_name,
                "audit_action": AuditAction.RESTORE.value,
                "new_values": new_values,
            },
        )
        
        logger.info(
            "Audit log created for RESTORE",
            client_id=str(client_id),
            table_name=table_name,
            record_id=str(record_id),
            user_id=str(user_id) if user_id else None
        )
        
        return saved_audit_log
    
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
