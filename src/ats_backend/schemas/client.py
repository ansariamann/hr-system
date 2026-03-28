"""Pydantic schemas for Client model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, validator


class ClientBase(BaseModel):
    """Base client schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Client organization name")
    industry: Optional[str] = Field(None, max_length=100, description="Industry classification")
    contact_name: Optional[str] = Field(None, max_length=255, description="Primary contact name")
    contact_email: Optional[EmailStr] = Field(None, description="Primary contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Primary contact phone")
    address: Optional[str] = Field(None, description="Client address")
    website: Optional[str] = Field(None, max_length=500, description="Client website URL")
    email_domain: Optional[str] = Field(None, max_length=255, description="Email domain for the client")
    is_active: bool = Field(default=True, description="Whether the client is active")
    
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
    industry: Optional[str] = Field(None, max_length=100)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    website: Optional[str] = Field(None, max_length=500)
    email_domain: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    
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


class ClientProvisionResponse(ClientResponse):
    """Response returned when provisioning a client with credentials."""

    credentials_generated: bool = False
    credentials_emailed: bool = False
    generated_email_path: Optional[str] = None
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    portal_login_url: Optional[str] = None


class ClientInviteResponse(BaseModel):
    """Response returned when generating a client invite link."""

    client_id: UUID
    invited_user_email: str
    invite_link: str
    expires_in: int
    invite_emailed: bool = False
    generated_email_path: Optional[str] = None
    token: Optional[str] = None
