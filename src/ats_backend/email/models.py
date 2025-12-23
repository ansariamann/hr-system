"""Email ingestion data models."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from uuid import UUID


class EmailAttachment(BaseModel):
    """Email attachment model."""
    
    filename: str = Field(..., description="Original filename of the attachment")
    content_type: str = Field(..., description="MIME content type")
    content: bytes = Field(..., description="Binary content of the attachment")
    size: int = Field(..., description="Size of the attachment in bytes")
    
    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename has supported extension."""
        if not v:
            raise ValueError("Filename cannot be empty")
        
        # Check for valid file extensions
        valid_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(f'File must have one of these extensions: {", ".join(valid_extensions)}')
        return v
    
    @validator('size')
    def validate_size(cls, v):
        """Validate file size is reasonable (max 50MB)."""
        max_size = 50 * 1024 * 1024  # 50MB
        if v > max_size:
            raise ValueError(f"File size {v} bytes exceeds maximum allowed size of {max_size} bytes")
        return v


class EmailMessage(BaseModel):
    """Email message model for ingestion."""
    
    message_id: str = Field(..., description="Unique email message ID for deduplication")
    sender: str = Field(..., description="Email sender address")
    subject: str = Field(..., description="Email subject line")
    body: Optional[str] = Field(None, description="Email body content")
    received_at: datetime = Field(default_factory=datetime.utcnow, description="When email was received")
    attachments: List[EmailAttachment] = Field(default_factory=list, description="Email attachments")
    headers: Dict[str, str] = Field(default_factory=dict, description="Email headers")
    
    @validator('message_id')
    def validate_message_id(cls, v):
        """Validate message ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Message ID cannot be empty")
        return v.strip()
    
    @validator('sender')
    def validate_sender(cls, v):
        """Validate sender email format."""
        if not v or '@' not in v:
            raise ValueError("Invalid sender email address")
        return v.lower()
    
    @validator('attachments')
    def validate_attachments(cls, v):
        """Validate at least one resume attachment exists."""
        if not v:
            raise ValueError("Email must contain at least one attachment")
        
        # Check that at least one attachment is a resume file
        valid_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']
        has_resume = any(
            any(att.filename.lower().endswith(ext) for ext in valid_extensions)
            for att in v
        )
        
        if not has_resume:
            raise ValueError("Email must contain at least one resume file (PDF, PNG, JPG, TIFF)")
        
        return v


class EmailIngestionRequest(BaseModel):
    """Request model for email ingestion API."""
    
    client_id: UUID = Field(..., description="Client UUID for multi-tenant isolation")
    email: EmailMessage = Field(..., description="Email message to process")
    
    class Config:
        json_encoders = {
            bytes: lambda v: v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else v
        }


class EmailIngestionResponse(BaseModel):
    """Response model for email ingestion API."""
    
    success: bool = Field(..., description="Whether ingestion was successful")
    message: str = Field(..., description="Status message")
    job_ids: List[UUID] = Field(default_factory=list, description="Created resume job IDs")
    duplicate_message_id: Optional[str] = Field(None, description="Message ID if duplicate detected")
    processed_attachments: int = Field(default=0, description="Number of attachments processed")
    
    class Config:
        json_encoders = {
            UUID: str
        }


class EmailProcessingStats(BaseModel):
    """Email processing statistics model."""
    
    total_emails_received: int = Field(default=0, description="Total emails received")
    total_attachments_processed: int = Field(default=0, description="Total attachments processed")
    duplicate_emails_rejected: int = Field(default=0, description="Duplicate emails rejected")
    failed_processing_count: int = Field(default=0, description="Failed processing attempts")
    average_processing_time_seconds: float = Field(default=0.0, description="Average processing time")
    last_processed_at: Optional[datetime] = Field(None, description="Last processing timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class FileStorageInfo(BaseModel):
    """File storage information model."""
    
    file_path: str = Field(..., description="Stored file path")
    original_filename: str = Field(..., description="Original filename")
    stored_filename: str = Field(..., description="Generated storage filename")
    content_type: str = Field(..., description="File content type")
    size_bytes: int = Field(..., description="File size in bytes")
    storage_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When file was stored")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }