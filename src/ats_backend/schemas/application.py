"""Pydantic schemas for Application model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ApplicationBase(BaseModel):
    """Base application schema with common fields."""
    
    candidate_id: UUID = Field(..., description="Candidate UUID")
    job_title: Optional[str] = Field(None, max_length=255, description="Job title for the application")
    application_date: Optional[datetime] = Field(None, description="Application date")
    status: str = Field(default="RECEIVED", description="Application status")
    flagged_for_review: bool = Field(default=False, description="Whether application is flagged for review")
    flag_reason: Optional[str] = Field(None, description="Reason for flagging")
    
    @validator('status')
    def validate_status(cls, v):
        """Validate application status."""
        valid_statuses = [
            'RECEIVED', 'SCREENING', 'INTERVIEW_SCHEDULED', 'INTERVIEWED', 
            'OFFER_MADE', 'HIRED', 'REJECTED', 'WITHDRAWN'
        ]
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v
    
    @validator('flag_reason')
    def validate_flag_reason(cls, v, values):
        """Validate flag reason is provided when flagged."""
        if values.get('flagged_for_review') and not v:
            raise ValueError('Flag reason is required when application is flagged for review')
        return v


class ApplicationCreate(ApplicationBase):
    """Schema for creating a new application."""
    pass


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    
    job_title: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = None
    flagged_for_review: Optional[bool] = None
    flag_reason: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        """Validate application status."""
        if v is not None:
            valid_statuses = [
                'RECEIVED', 'SCREENING', 'INTERVIEW_SCHEDULED', 'INTERVIEWED', 
                'OFFER_MADE', 'HIRED', 'REJECTED', 'WITHDRAWN'
            ]
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v
    
    @validator('flag_reason')
    def validate_flag_reason(cls, v, values):
        """Validate flag reason is provided when flagged."""
        if values.get('flagged_for_review') and not v:
            raise ValueError('Flag reason is required when application is flagged for review')
        return v


class ApplicationResponse(ApplicationBase):
    """Schema for application response."""
    
    id: UUID
    client_id: UUID
    deleted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = Field(description="Whether application is soft deleted")
    
    class Config:
        from_attributes = True