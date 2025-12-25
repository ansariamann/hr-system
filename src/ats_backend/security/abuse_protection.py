"""Abuse protection and input validation for the ATS system."""

import asyncio
import hashlib
import mimetypes
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.config import settings
from ats_backend.core.redis import get_redis
from ats_backend.auth.security import SecurityLogger, SecurityEventType, SecurityEventSeverity
from ats_backend.email.models import EmailAttachment, EmailMessage

logger = structlog.get_logger(__name__)


class AbuseProtectionConfig:
    """Configuration for abuse protection mechanisms."""
    
    # File validation limits
    MAX_ATTACHMENT_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    MAX_RESUMES_PER_EMAIL = 10
    MAX_FILENAME_LENGTH = 255
    
    # Rate limiting (requests per time window)
    RATE_LIMITS = {
        "email_ingestion": {"limit": 10, "window": 60},      # 10 per minute per IP
        "api_requests": {"limit": 1000, "window": 3600},     # 1000 per hour per client
        "login_attempts": {"limit": 5, "window": 900},       # 5 per 15 minutes per IP
        "file_uploads": {"limit": 50, "window": 3600},       # 50 per hour per IP
    }
    
    # Allowed MIME types for resume files
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/png", 
        "image/jpeg",
        "image/tiff",
        "image/tif"
    }
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"
    }
    
    # Dangerous file patterns to block
    DANGEROUS_PATTERNS = [
        r"\.\.\/",  # Path traversal
        r"\.\.\\",  # Windows path traversal
        r"\/etc\/",  # Unix system files
        r"\/proc\/",  # Unix process files
        r"\/sys\/",  # Unix system files
        r"C:\\Windows\\",  # Windows system files
        r"C:\\Program Files\\",  # Windows program files
        r"<script",  # Script injection
        r"javascript:",  # JavaScript protocol
        r"data:",  # Data URLs
        r"vbscript:",  # VBScript protocol
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
        r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
        r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
        r"(--|\/\*|\*\/)",
        r"(\bxp_cmdshell\b)",
        r"(\bsp_executesql\b)",
    ]


class RateLimiter:
    """Redis-based rate limiter for abuse protection."""
    
    def __init__(self, redis_client=None):
        """Initialize rate limiter.
        
        Args:
            redis_client: Redis client instance (optional)
        """
        self.redis = redis_client or get_redis()
        self.security_logger = SecurityLogger()
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit_type: str, 
        identifier: str,
        request: Optional[Request] = None
    ) -> bool:
        """Check if request is within rate limits.
        
        Args:
            key: Rate limit key (e.g., IP address, client ID)
            limit_type: Type of rate limit to check
            identifier: Human-readable identifier for logging
            request: FastAPI request object for additional context
            
        Returns:
            True if within limits, False if rate limited
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        if limit_type not in AbuseProtectionConfig.RATE_LIMITS:
            logger.warning("Unknown rate limit type", limit_type=limit_type)
            return True
        
        config = AbuseProtectionConfig.RATE_LIMITS[limit_type]
        limit = config["limit"]
        window = config["window"]
        
        # Create Redis key
        redis_key = f"rate_limit:{limit_type}:{key}"
        
        try:
            # Get current count
            current = await self.redis.get(redis_key)
            current_count = int(current) if current else 0
            
            if current_count >= limit:
                # Rate limit exceeded
                await self._log_rate_limit_violation(
                    key, limit_type, identifier, current_count, limit, request
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {limit_type}. "
                           f"Limit: {limit} requests per {window} seconds"
                )
            
            # Increment counter
            pipe = self.redis.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window)
            await pipe.execute()
            
            logger.debug(
                "Rate limit check passed",
                key=key,
                limit_type=limit_type,
                current_count=current_count + 1,
                limit=limit
            )
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Rate limit check failed",
                key=key,
                limit_type=limit_type,
                error=str(e)
            )
            # Fail open - allow request if Redis is down
            return True
    
    async def _log_rate_limit_violation(
        self,
        key: str,
        limit_type: str,
        identifier: str,
        current_count: int,
        limit: int,
        request: Optional[Request] = None
    ):
        """Log rate limit violation as security event."""
        details = {
            "rate_limit_key": key,
            "limit_type": limit_type,
            "identifier": identifier,
            "current_count": current_count,
            "limit": limit,
            "violation_time": datetime.utcnow().isoformat()
        }
        
        if request:
            details.update({
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "path": str(request.url.path),
                "method": request.method
            })
        
        await self.security_logger.log_security_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SecurityEventSeverity.MEDIUM,
            details=details,
            client_id=getattr(request.state, 'current_client_id', None) if request else None,
            user_id=getattr(request.state, 'current_user_id', None) if request else None,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None
        )


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    def __init__(self):
        """Initialize input validator."""
        self.security_logger = SecurityLogger()
        
        # Compile regex patterns for performance
        self.dangerous_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in AbuseProtectionConfig.DANGEROUS_PATTERNS
        ]
        
        self.sql_injection_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in AbuseProtectionConfig.SQL_INJECTION_PATTERNS
        ]
    
    def validate_filename(self, filename: str, request: Optional[Request] = None) -> str:
        """Validate and sanitize filename.
        
        Args:
            filename: Original filename
            request: FastAPI request for logging context
            
        Returns:
            Sanitized filename
            
        Raises:
            HTTPException: If filename is invalid or dangerous
        """
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty"
            )
        
        filename = filename.strip()
        
        # Check length
        if len(filename) > AbuseProtectionConfig.MAX_FILENAME_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filename too long (max {AbuseProtectionConfig.MAX_FILENAME_LENGTH} characters)"
            )
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if pattern.search(filename):
                self._log_dangerous_input(
                    "filename", filename, pattern.pattern, request
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Filename contains invalid characters or patterns"
                )
        
        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in AbuseProtectionConfig.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(AbuseProtectionConfig.ALLOWED_EXTENSIONS)}"
            )
        
        # Sanitize filename - remove/replace dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'\.{2,}', '.', sanitized)  # Replace multiple dots
        
        return sanitized
    
    def validate_mime_type(self, content_type: str, filename: str, request: Optional[Request] = None) -> bool:
        """Validate MIME type against allowed types.
        
        Args:
            content_type: MIME content type
            filename: Original filename for additional validation
            request: FastAPI request for logging context
            
        Returns:
            True if MIME type is allowed
            
        Raises:
            HTTPException: If MIME type is not allowed
        """
        if not content_type:
            # Try to guess from filename
            guessed_type, _ = mimetypes.guess_type(filename)
            content_type = guessed_type or "application/octet-stream"
        
        # Normalize MIME type
        content_type = content_type.lower().split(';')[0].strip()
        
        if content_type not in AbuseProtectionConfig.ALLOWED_MIME_TYPES:
            self._log_invalid_mime_type(content_type, filename, request)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Content-Type: {content_type}"
            )
        
        return True
    
    def validate_file_size(self, size: int, request: Optional[Request] = None) -> bool:
        """Validate file size against limits.
        
        Args:
            size: File size in bytes
            request: FastAPI request for logging context
            
        Returns:
            True if size is within limits
            
        Raises:
            HTTPException: If file size exceeds limits
        """
        if size > AbuseProtectionConfig.MAX_ATTACHMENT_SIZE_BYTES:
            self._log_oversized_file(size, request)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size {size} bytes exceeds maximum allowed size of "
                       f"{AbuseProtectionConfig.MAX_ATTACHMENT_SIZE_BYTES} bytes"
            )
        
        return True
    
    def validate_text_input(self, text: str, field_name: str, request: Optional[Request] = None) -> str:
        """Validate and sanitize text input for SQL injection and XSS.
        
        Args:
            text: Input text to validate
            field_name: Name of the field being validated
            request: FastAPI request for logging context
            
        Returns:
            Sanitized text
            
        Raises:
            HTTPException: If text contains dangerous patterns
        """
        if not text:
            return text
        
        # Check for SQL injection patterns
        for pattern in self.sql_injection_patterns:
            if pattern.search(text):
                self._log_sql_injection_attempt(
                    field_name, text, pattern.pattern, request
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid input detected in {field_name}"
                )
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if pattern.search(text):
                self._log_dangerous_input(
                    field_name, text, pattern.pattern, request
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid input detected in {field_name}"
                )
        
        # Basic XSS protection - escape HTML entities
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        text = text.replace('"', '&quot;').replace("'", '&#x27;')
        
        return text
    
    def _log_dangerous_input(
        self, 
        field_name: str, 
        input_value: str, 
        pattern: str, 
        request: Optional[Request] = None
    ):
        """Log dangerous input attempt."""
        details = {
            "field_name": field_name,
            "input_value": input_value[:200],  # Truncate for logging
            "matched_pattern": pattern,
            "detection_time": datetime.utcnow().isoformat()
        }
        
        asyncio.create_task(
            self.security_logger.log_security_event(
                event_type=SecurityEventType.MALICIOUS_INPUT_DETECTED,
                severity=SecurityEventSeverity.HIGH,
                details=details,
                client_id=getattr(request.state, 'current_client_id', None) if request else None,
                user_id=getattr(request.state, 'current_user_id', None) if request else None,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent") if request else None
            )
        )
    
    def _log_sql_injection_attempt(
        self, 
        field_name: str, 
        input_value: str, 
        pattern: str, 
        request: Optional[Request] = None
    ):
        """Log SQL injection attempt."""
        details = {
            "field_name": field_name,
            "input_value": input_value[:200],  # Truncate for logging
            "matched_pattern": pattern,
            "attack_type": "sql_injection",
            "detection_time": datetime.utcnow().isoformat()
        }
        
        asyncio.create_task(
            self.security_logger.log_security_event(
                event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                severity=SecurityEventSeverity.CRITICAL,
                details=details,
                client_id=getattr(request.state, 'current_client_id', None) if request else None,
                user_id=getattr(request.state, 'current_user_id', None) if request else None,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent") if request else None
            )
        )
    
    def _log_invalid_mime_type(
        self, 
        content_type: str, 
        filename: str, 
        request: Optional[Request] = None
    ):
        """Log invalid MIME type attempt."""
        details = {
            "content_type": content_type,
            "filename": filename,
            "allowed_types": list(AbuseProtectionConfig.ALLOWED_MIME_TYPES),
            "detection_time": datetime.utcnow().isoformat()
        }
        
        asyncio.create_task(
            self.security_logger.log_security_event(
                event_type=SecurityEventType.INVALID_FILE_TYPE,
                severity=SecurityEventSeverity.MEDIUM,
                details=details,
                client_id=getattr(request.state, 'current_client_id', None) if request else None,
                user_id=getattr(request.state, 'current_user_id', None) if request else None,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent") if request else None
            )
        )
    
    def _log_oversized_file(self, size: int, request: Optional[Request] = None):
        """Log oversized file attempt."""
        details = {
            "file_size": size,
            "max_allowed_size": AbuseProtectionConfig.MAX_ATTACHMENT_SIZE_BYTES,
            "detection_time": datetime.utcnow().isoformat()
        }
        
        asyncio.create_task(
            self.security_logger.log_security_event(
                event_type=SecurityEventType.FILE_SIZE_EXCEEDED,
                severity=SecurityEventSeverity.MEDIUM,
                details=details,
                client_id=getattr(request.state, 'current_client_id', None) if request else None,
                user_id=getattr(request.state, 'current_user_id', None) if request else None,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent") if request else None
            )
        )


class AbuseProtectionService:
    """Main service for abuse protection and input validation."""
    
    def __init__(self, redis_client=None):
        """Initialize abuse protection service.
        
        Args:
            redis_client: Redis client instance (optional)
        """
        self.rate_limiter = RateLimiter(redis_client)
        self.input_validator = InputValidator()
        self.security_logger = SecurityLogger()
    
    async def validate_email_ingestion(
        self, 
        request: Request, 
        email: EmailMessage,
        client_id: UUID
    ) -> bool:
        """Comprehensive validation for email ingestion requests.
        
        Args:
            request: FastAPI request object
            email: Email message to validate
            client_id: Client UUID for context
            
        Returns:
            True if validation passes
            
        Raises:
            HTTPException: If validation fails
        """
        # Get IP address for rate limiting
        ip_address = request.client.host if request.client else "unknown"
        
        # Check IP-based rate limiting for email ingestion
        await self.rate_limiter.check_rate_limit(
            key=ip_address,
            limit_type="email_ingestion",
            identifier=f"IP {ip_address}",
            request=request
        )
        
        # Check client-based rate limiting for API requests
        await self.rate_limiter.check_rate_limit(
            key=str(client_id),
            limit_type="api_requests", 
            identifier=f"Client {client_id}",
            request=request
        )
        
        # Validate email message fields
        email.sender = self.input_validator.validate_text_input(
            email.sender, "sender", request
        )
        email.subject = self.input_validator.validate_text_input(
            email.subject, "subject", request
        )
        if email.body:
            email.body = self.input_validator.validate_text_input(
                email.body, "body", request
            )
        
        # Validate attachment count
        if len(email.attachments) > AbuseProtectionConfig.MAX_RESUMES_PER_EMAIL:
            await self._log_attachment_count_violation(
                len(email.attachments), client_id, request
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many attachments. Maximum allowed: {AbuseProtectionConfig.MAX_RESUMES_PER_EMAIL}"
            )
        
        # Validate each attachment
        for i, attachment in enumerate(email.attachments):
            await self.validate_attachment(attachment, request, f"attachment_{i}")
        
        logger.info(
            "Email ingestion validation passed",
            client_id=str(client_id),
            ip_address=ip_address,
            attachment_count=len(email.attachments)
        )
        
        return True
    
    async def validate_attachment(
        self, 
        attachment: EmailAttachment, 
        request: Optional[Request] = None,
        context: str = "attachment"
    ) -> bool:
        """Validate individual email attachment.
        
        Args:
            attachment: Email attachment to validate
            request: FastAPI request for context
            context: Context string for logging
            
        Returns:
            True if validation passes
            
        Raises:
            HTTPException: If validation fails
        """
        # Validate filename
        attachment.filename = self.input_validator.validate_filename(
            attachment.filename, request
        )
        
        # Validate MIME type
        self.input_validator.validate_mime_type(
            attachment.content_type, attachment.filename, request
        )
        
        # Validate file size
        self.input_validator.validate_file_size(attachment.size, request)
        
        # Additional file content validation could be added here
        # (e.g., magic number validation, virus scanning)
        
        return True
    
    async def validate_file_upload(
        self, 
        request: Request,
        filename: str,
        content_type: str,
        file_size: int,
        client_id: Optional[UUID] = None
    ) -> bool:
        """Validate file upload requests.
        
        Args:
            request: FastAPI request object
            filename: Original filename
            content_type: MIME content type
            file_size: File size in bytes
            client_id: Client UUID for context
            
        Returns:
            True if validation passes
            
        Raises:
            HTTPException: If validation fails
        """
        # Get IP address for rate limiting
        ip_address = request.client.host if request.client else "unknown"
        
        # Check IP-based rate limiting for file uploads
        await self.rate_limiter.check_rate_limit(
            key=ip_address,
            limit_type="file_uploads",
            identifier=f"IP {ip_address}",
            request=request
        )
        
        # Validate filename
        sanitized_filename = self.input_validator.validate_filename(filename, request)
        
        # Validate MIME type
        self.input_validator.validate_mime_type(content_type, filename, request)
        
        # Validate file size
        self.input_validator.validate_file_size(file_size, request)
        
        logger.info(
            "File upload validation passed",
            filename=sanitized_filename,
            content_type=content_type,
            file_size=file_size,
            client_id=str(client_id) if client_id else None,
            ip_address=ip_address
        )
        
        return True
    
    async def _log_attachment_count_violation(
        self, 
        count: int, 
        client_id: UUID, 
        request: Request
    ):
        """Log attachment count violation."""
        details = {
            "attachment_count": count,
            "max_allowed": AbuseProtectionConfig.MAX_RESUMES_PER_EMAIL,
            "client_id": str(client_id),
            "detection_time": datetime.utcnow().isoformat()
        }
        
        await self.security_logger.log_security_event(
            event_type=SecurityEventType.ATTACHMENT_LIMIT_EXCEEDED,
            severity=SecurityEventSeverity.MEDIUM,
            details=details,
            client_id=client_id,
            user_id=getattr(request.state, 'current_user_id', None),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )


# Global instance for easy import
abuse_protection = AbuseProtectionService()