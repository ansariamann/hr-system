"""Security utilities for authentication hardening."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.base import Base
from ats_backend.core.redis import get_redis

logger = structlog.get_logger(__name__)


class SecurityEventType(str, Enum):
    """Security event types for audit logging."""
    AUTH_FAILURE = "auth_failure"
    TOKEN_REPLAY = "token_replay"
    EXPIRED_TOKEN = "expired_token"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ACCOUNT_LOCKED = "account_locked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RLS_BYPASS_ATTEMPT = "rls_bypass_attempt"
    MALICIOUS_INPUT_DETECTED = "malicious_input_detected"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    INVALID_FILE_TYPE = "invalid_file_type"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    ATTACHMENT_LIMIT_EXCEEDED = "attachment_limit_exceeded"


class SecurityEventSeverity(str, Enum):
    """Security event severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityAuditLog(Base):
    """Security audit log model."""
    
    __tablename__ = "security_audit_logs"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    client_id = Column(PG_UUID(as_uuid=True), nullable=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<SecurityAuditLog(id={self.id}, event_type={self.event_type}, severity={self.severity})>"


class TokenReplayProtection:
    """Token replay protection using Redis."""
    
    def __init__(self):
        self.token_ttl = 3600  # 1 hour
    
    async def validate_token_usage(self, token_jti: str) -> bool:
        """Validate that a token hasn't been used before.
        
        Args:
            token_jti: JWT ID (jti) claim from token
            
        Returns:
            True if token is valid for use, False if already used
        """
        try:
            redis_client = await get_redis()
            key = f"token_used:{token_jti}"
            
            # Check if token was already used
            if await redis_client.exists(key):
                logger.warning("Token replay attempt detected", token_jti=token_jti)
                return False
            
            # Mark token as used
            await redis_client.setex(key, self.token_ttl, "1")
            return True
            
        except Exception as e:
            logger.error("Token replay protection failed", error=str(e), token_jti=token_jti)
            # Fail secure - reject token if we can't validate
            return False
    
    async def invalidate_token(self, token_jti: str) -> bool:
        """Invalidate a token immediately.
        
        Args:
            token_jti: JWT ID (jti) claim from token
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await get_redis()
            key = f"token_used:{token_jti}"
            await redis_client.setex(key, self.token_ttl, "1")
            return True
            
        except Exception as e:
            logger.error("Token invalidation failed", error=str(e), token_jti=token_jti)
            return False


class RateLimiter:
    """Rate limiting for authentication attempts."""
    
    def __init__(self):
        from ats_backend.core.config import settings
        self.login_attempts_limit = settings.login_attempts_limit
        self.login_window_minutes = settings.login_window_minutes
        self.lockout_duration_minutes = settings.lockout_duration_minutes
    
    async def check_rate_limit(self, identifier: str, limit_type: str = "login") -> tuple[bool, int]:
        """Check if rate limit is exceeded.
        
        Args:
            identifier: IP address or user identifier
            limit_type: Type of rate limit (login, api, etc.)
            
        Returns:
            Tuple of (is_allowed, remaining_attempts)
        """
        try:
            redis_client = await get_redis()
            key = f"rate_limit:{limit_type}:{identifier}"
            
            current_count = await redis_client.get(key)
            if current_count is None:
                current_count = 0
            else:
                current_count = int(current_count)
            
            if limit_type == "login":
                limit = self.login_attempts_limit
                window = self.login_window_minutes * 60
            else:
                limit = 100  # Default limit
                window = 3600  # 1 hour
            
            if current_count >= limit:
                return False, 0
            
            return True, limit - current_count
            
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e), identifier=identifier)
            # Fail open for availability
            return True, 999
    
    async def record_attempt(self, identifier: str, limit_type: str = "login") -> None:
        """Record an attempt for rate limiting.
        
        Args:
            identifier: IP address or user identifier
            limit_type: Type of rate limit (login, api, etc.)
        """
        try:
            redis_client = await get_redis()
            key = f"rate_limit:{limit_type}:{identifier}"
            
            if limit_type == "login":
                window = self.login_window_minutes * 60
            else:
                window = 3600  # 1 hour
            
            # Increment counter with expiration
            await redis_client.incr(key)
            await redis_client.expire(key, window)
            
        except Exception as e:
            logger.error("Rate limit recording failed", error=str(e), identifier=identifier)
    
    async def is_account_locked(self, email: str) -> tuple[bool, Optional[datetime]]:
        """Check if account is locked due to too many failed attempts.
        
        Args:
            email: User email address
            
        Returns:
            Tuple of (is_locked, unlock_time)
        """
        try:
            redis_client = await get_redis()
            key = f"account_locked:{email}"
            
            lock_data = await redis_client.get(key)
            if lock_data is None:
                return False, None
            
            # Parse lock timestamp
            lock_timestamp = datetime.fromisoformat(lock_data)
            unlock_time = lock_timestamp + timedelta(minutes=self.lockout_duration_minutes)
            
            if datetime.utcnow() >= unlock_time:
                # Lock expired, remove it
                await redis_client.delete(key)
                return False, None
            
            return True, unlock_time
            
        except Exception as e:
            logger.error("Account lock check failed", error=str(e), email=email)
            return False, None
    
    async def lock_account(self, email: str) -> None:
        """Lock an account due to too many failed attempts.
        
        Args:
            email: User email address
        """
        try:
            redis_client = await get_redis()
            key = f"account_locked:{email}"
            lock_timestamp = datetime.utcnow().isoformat()
            
            await redis_client.setex(
                key, 
                self.lockout_duration_minutes * 60, 
                lock_timestamp
            )
            
            logger.warning("Account locked due to failed attempts", email=email)
            
        except Exception as e:
            logger.error("Account locking failed", error=str(e), email=email)


class SecurityLogger:
    """Security event logging utility."""
    
    @staticmethod
    def log_security_event(
        db: Session,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        details: Dict[str, Any],
        client_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        email: Optional[str] = None
    ) -> SecurityAuditLog:
        """Log a security event to the audit log.
        
        Args:
            db: Database session
            event_type: Type of security event
            severity: Severity level
            details: Additional event details
            client_id: Optional client ID
            user_id: Optional user ID
            ip_address: Optional IP address
            user_agent: Optional user agent
            email: Optional email address
            
        Returns:
            Created security audit log entry
        """
        try:
            audit_log = SecurityAuditLog(
                event_type=event_type,
                severity=severity,
                client_id=client_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                email=email,
                details=details
            )
            
            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)
            
            logger.warning(
                "Security event logged",
                event_type=event_type.value,
                severity=severity.value,
                details=details,
                audit_id=str(audit_log.id)
            )
            
            return audit_log
            
        except Exception as e:
            logger.error("Failed to log security event", error=str(e))
            db.rollback()
            raise
    
    @staticmethod
    async def log_security_event_async(
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        details: Dict[str, Any],
        client_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        email: Optional[str] = None
    ) -> None:
        """Async version of security event logging.
        
        Args:
            event_type: Type of security event
            severity: Severity level
            details: Additional event details
            client_id: Optional client ID
            user_id: Optional user ID
            ip_address: Optional IP address
            user_agent: Optional user agent
            email: Optional email address
        """
        try:
            from ats_backend.core.database import get_db
            
            # Get database session
            db_gen = get_db()
            db: Session = next(db_gen)
            
            try:
                audit_log = SecurityAuditLog(
                    event_type=event_type,
                    severity=severity,
                    client_id=client_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    email=email,
                    details=details
                )
                
                db.add(audit_log)
                db.commit()
                
                logger.warning(
                    "Security event logged",
                    event_type=event_type.value,
                    severity=severity.value,
                    details=details,
                    audit_id=str(audit_log.id)
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error("Failed to log security event", error=str(e))


# Global instances
token_replay_protection = TokenReplayProtection()
rate_limiter = RateLimiter()
security_logger = SecurityLogger()