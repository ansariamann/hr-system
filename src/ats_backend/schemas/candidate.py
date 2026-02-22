"""Pydantic schemas for Candidate model."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, validator, root_validator


class CandidateBase(BaseModel):
    """Base candidate schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Candidate full name")
    email: Optional[EmailStr] = Field(None, description="Candidate email address")
    phone: Optional[str] = Field(None, max_length=50, description="Candidate phone number")
    location: Optional[str] = Field(None, max_length=255, description="Candidate location/city")
    present_address: Optional[str] = Field(None, description="Current/present address")
    permanent_address: Optional[str] = Field(None, description="Permanent address")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    previous_employment: Optional[List[Dict[str, Any]]] = Field(None, description="Previous employment history")
    key_skill: Optional[str] = Field(None, description="Key skill summary")
    resume_file_path: Optional[str] = Field(None, description="Path/URL for uploaded resume file")
    resume_url: Optional[str] = Field(None, description="Canonical resume URL/path")
    assigned_user_id: Optional[UUID] = Field(None, description="User assigned to this candidate")
    skills: Optional[Dict[str, Any]] = Field(None, description="Candidate skills in JSONB format")
    experience: Optional[Dict[str, Any]] = Field(None, description="Candidate experience in JSONB format")
    ctc_current: Optional[Decimal] = Field(None, ge=0, description="Current CTC in decimal format")
    ctc_expected: Optional[Decimal] = Field(None, ge=0, description="Expected CTC in decimal format")
    status: str = Field(default="ACTIVE", description="Candidate status")
    remark: Optional[str] = Field(None, description="Candidate remarks or notes")
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v is not None:
            # Remove common separators for validation
            cleaned = v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
            if not cleaned.isdigit():
                raise ValueError('Phone number should contain only digits and common separators')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        """Validate candidate status."""
        valid_statuses = ['ACTIVE', 'INACTIVE', 'LEFT', 'HIRED', 'REJECTED']
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v
    
    @validator('skills')
    def validate_skills(cls, v):
        """Validate skills format."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError('Skills must be a dictionary')
            # Ensure skills list exists and is a list
            if 'skills' in v and not isinstance(v['skills'], list):
                raise ValueError('Skills.skills must be a list')
        return v
    
    @validator('experience')
    def validate_experience(cls, v):
        """Validate experience format."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError('Experience must be a dictionary')
        return v

    @root_validator(pre=True)
    def normalize_resume_fields(cls, values):
        """Keep legacy and canonical resume fields in sync."""
        if not isinstance(values, dict):
            return values
        resume_url = values.get("resume_url")
        resume_file_path = values.get("resume_file_path")
        if resume_url and not resume_file_path:
            values["resume_file_path"] = resume_url
        if resume_file_path and not resume_url:
            values["resume_url"] = resume_file_path
        return values


class CandidateCreate(CandidateBase):
    """Schema for creating a new candidate."""
    candidate_hash: Optional[str] = Field(None, max_length=64, description="Candidate hash for duplicate detection")


class CandidateUpdate(BaseModel):
    """Schema for updating a candidate."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=255)
    present_address: Optional[str] = None
    permanent_address: Optional[str] = None
    date_of_birth: Optional[date] = None
    previous_employment: Optional[List[Dict[str, Any]]] = None
    key_skill: Optional[str] = None
    resume_file_path: Optional[str] = None
    resume_url: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    skills: Optional[Dict[str, Any]] = None
    experience: Optional[Dict[str, Any]] = None
    ctc_current: Optional[Decimal] = Field(None, ge=0)
    ctc_expected: Optional[Decimal] = Field(None, ge=0)
    status: Optional[str] = None
    remark: Optional[str] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v is not None:
            cleaned = v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
            if not cleaned.isdigit():
                raise ValueError('Phone number should contain only digits and common separators')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        """Validate candidate status."""
        if v is not None:
            valid_statuses = ['ACTIVE', 'INACTIVE', 'LEFT', 'HIRED', 'REJECTED']
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v
    
    @validator('skills')
    def validate_skills(cls, v):
        """Validate skills format."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError('Skills must be a dictionary')
            if 'skills' in v and not isinstance(v['skills'], list):
                raise ValueError('Skills.skills must be a list')
        return v
    
    @validator('experience')
    def validate_experience(cls, v):
        """Validate experience format."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError('Experience must be a dictionary')
        return v

    @root_validator(pre=True)
    def normalize_resume_fields(cls, values):
        """Keep legacy and canonical resume fields in sync."""
        if not isinstance(values, dict):
            return values
        resume_url = values.get("resume_url")
        resume_file_path = values.get("resume_file_path")
        if resume_url and not resume_file_path:
            values["resume_file_path"] = resume_url
        if resume_file_path and not resume_url:
            values["resume_url"] = resume_file_path
        return values


class CandidateResponse(CandidateBase):
    """Schema for candidate response."""
    
    id: UUID
    client_id: UUID
    assigned_user_id: Optional[UUID]
    candidate_hash: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
