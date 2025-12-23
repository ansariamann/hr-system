"""Pydantic schemas for ResumeJob model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ResumeJobBase(BaseModel):
    """Base resume job schema with common fields."""
    
    email_message_id: Optional[str] = Field(None, max_length=255, description="Email message ID for deduplication")
    file_name: Optional[str] = Field(None, max_length=255, description="Resume file name")
    file_path: Optional[str] = Field(None, description="Path to resume file")
    status: str = Field(default="PENDING", description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    
    @validator('status')
    def validate_status(cls, v):
        """Validate resume job status."""
        valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v
    
    @validator('file_name')
    def validate_file_name(cls, v):
        """Validate file name format."""
        if v is not None:
            # Check for valid file extensions
            valid_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']
            if not any(v.lower().endswith(ext) for ext in valid_extensions):
                raise ValueError(f'File must have one of these extensions: {", ".join(valid_extensions)}')
        return v


class ResumeJobCreate(ResumeJobBase):
    """Schema for creating a new resume job."""
    pass


class ResumeJobUpdate(BaseModel):
    """Schema for updating a resume job."""
    
    status: Optional[str] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    @validator('status')
    def validate_status(cls, v):
        """Validate resume job status."""
        if v is not None:
            valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v


class ResumeJobResponse(ResumeJobBase):
    """Schema for resume job response."""
    
    id: UUID
    client_id: UUID
    processed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True