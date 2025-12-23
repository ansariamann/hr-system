"""Pydantic schemas for Client model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, validator


class ClientBase(BaseModel):
    """Base client schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Client organization name")
    email_domain: Optional[str] = Field(None, max_length=255, description="Email domain for the client")
    
    @validator('email_domain')
    def validate_email_domain(cls, v):
        """Validate email domain format."""
        if v is not None:
            # Basic domain validation - should not contain @ or spaces
            if '@' in v or ' ' in v:
                raise ValueError('Email domain should not contain @ or spaces')
            # Should contain at least one dot
            if '.' not in v:
                raise ValueError('Email domain should contain at least one dot')
        return v


class ClientCreate(ClientBase):
    """Schema for creating a new client."""
    pass


class ClientUpdate(BaseModel):
    """Schema for updating a client."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email_domain: Optional[str] = Field(None, max_length=255)
    
    @validator('email_domain')
    def validate_email_domain(cls, v):
        """Validate email domain format."""
        if v is not None:
            if '@' in v or ' ' in v:
                raise ValueError('Email domain should not contain @ or spaces')
            if '.' not in v:
                raise ValueError('Email domain should contain at least one dot')
        return v


class ClientResponse(ClientBase):
    """Schema for client response."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True