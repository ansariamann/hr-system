"""Pydantic schemas for Application model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator
from ats_backend.schemas.candidate import CandidateResponse


APPLICATION_STATUS_ALIASES = {
    "NEW": "RECEIVED",
    "RECEIVED": "RECEIVED",
    "IN_REVIEW": "SCREENING",
    "SCREENING": "SCREENING",
    "SHORTLISTED": "INTERVIEW_SCHEDULED",
    "INTERVIEW_SCHEDULED": "INTERVIEW_SCHEDULED",
    "INTERVIEW": "INTERVIEWED",
    "INTERVIEWED": "INTERVIEWED",
    "OFFER": "OFFER_MADE",
    "OFFER_MADE": "OFFER_MADE",
    "ACCEPTED": "HIRED",
    "HIRED": "HIRED",
    "DECLINED": "WITHDRAWN",
    "WITHDRAWN": "WITHDRAWN",
    "REJECTED": "REJECTED",
}


def normalize_application_status(value: str) -> str:
    """Normalize legacy and current application statuses to the canonical backend values."""
    if value is None:
        return value

    normalized = APPLICATION_STATUS_ALIASES.get(value.strip().upper())
    if not normalized:
        valid_statuses = sorted(set(APPLICATION_STATUS_ALIASES.values()))
        raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
    return normalized


class ApplicationBase(BaseModel):
    """Base application schema with common fields."""
    
    candidate_id: UUID = Field(..., description="Candidate UUID")
    job_id: Optional[UUID] = Field(None, description="Job UUID linked to the application")
    job_title: Optional[str] = Field(None, max_length=255, description="Job title for the application")
    application_date: Optional[datetime] = Field(None, description="Application date")
    source: Optional[str] = Field("MANUAL", max_length=100, description="Application source channel")
    status: str = Field(default="RECEIVED", description="Application status")
    notes: Optional[str] = Field(None, description="Internal notes for the application")
    flagged_for_review: bool = Field(default=False, description="Whether application is flagged for review")
    flag_reason: Optional[str] = Field(None, description="Reason for flagging")
    
    @validator('status')
    def validate_status(cls, v):
        """Validate application status."""
        return normalize_application_status(v)
    
    @validator('flag_reason')
    def validate_flag_reason(cls, v, values):
        """Validate flag reason is provided when flagged."""
        if values.get('flagged_for_review') and not v:
            raise ValueError('Flag reason is required when application is flagged for review')
        return v


class ApplicationCreate(ApplicationBase):
    """Schema for creating a new application."""
    job_id: UUID = Field(..., description="Job UUID linked to the application")
    client_id: Optional[UUID] = Field(
        None, description="Target client UUID; defaults to current authenticated client if omitted"
    )


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    
    job_id: Optional[UUID] = None
    job_title: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    notes: Optional[str] = None
    flagged_for_review: Optional[bool] = None
    flag_reason: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        """Validate application status."""
        if v is not None:
            return normalize_application_status(v)
        return v
    
    @validator('flag_reason')
    def validate_flag_reason(cls, v, values):
        """Validate flag reason is provided when flagged."""
        if values.get('flagged_for_review') and not v:
            raise ValueError('Flag reason is required when application is flagged for review')
        return v


class HrInterviewAcknowledgeRequest(BaseModel):
    """Request payload for HR interview acknowledgement."""

    note: Optional[str] = Field(None, description="Optional note sent with HR acknowledgement")


class ApplicationResponse(ApplicationBase):
    """Schema for application response."""
    
    id: UUID
    client_id: UUID
    applied_by_user_id: Optional[UUID]
    hr_interview_acknowledged: bool
    hr_interview_acknowledged_at: Optional[datetime]
    hr_interview_acknowledged_by: Optional[UUID]
    hr_interview_ack_note: Optional[str]
    deleted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    status_updated_at: datetime
    is_deleted: bool = Field(description="Whether application is soft deleted")
    candidate: Optional[CandidateResponse] = None
    client_name: Optional[str] = Field(None, description="Client name for display")
    
    @validator('client_name', pre=True, always=True)
    def populate_client_name(cls, v, values):
        """Populate client_name from the client relationship if available."""
        return v
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm_with_client(cls, obj):
        """Create response from ORM object, extracting client name from relationship."""
        data = cls.from_orm(obj) if hasattr(cls, 'from_orm') else cls.model_validate(obj)
        if hasattr(obj, 'client') and obj.client is not None:
            data.client_name = obj.client.name
        return data
