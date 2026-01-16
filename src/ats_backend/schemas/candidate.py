"""Pydantic schemas for Candidate model."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, validator


class CandidateBase(BaseModel):
    """Base candidate schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Candidate full name")
    email: Optional[EmailStr] = Field(None, description="Candidate email address")
    phone: Optional[str] = Field(None, max_length=50, description="Candidate phone number")
    location: Optional[str] = Field(None, max_length=255, description="Candidate location/city")
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


class CandidateCreate(CandidateBase):
    """Schema for creating a new candidate."""
    candidate_hash: Optional[str] = Field(None, max_length=64, description="Candidate hash for duplicate detection")


class CandidateUpdate(BaseModel):
    """Schema for updating a candidate."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=255)
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


class CandidateResponse(CandidateBase):
    """Schema for candidate response."""
    
    id: UUID
    client_id: UUID
    candidate_hash: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True