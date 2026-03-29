"""Pydantic schemas for CompanyEmployee model."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


EMPLOYEE_STATUSES = ["ACTIVE", "INACTIVE", "LEFT"]


class CompanyEmployeeBase(BaseModel):
    """Base schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Employee full name")
    email: Optional[str] = Field(None, max_length=255, description="Employee email")
    phone: Optional[str] = Field(None, max_length=50, description="Employee phone number")
    role: Optional[str] = Field(None, max_length=255, description="Job title / role")
    department: Optional[str] = Field(None, max_length=255, description="Department")
    date_of_joining: Optional[date] = Field(None, description="Date of joining")
    status: str = Field(default="ACTIVE", description="Employee status")
    is_active: bool = Field(default=True, description="Whether employee is currently active")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator("status")
    def validate_status(cls, v):
        if v not in EMPLOYEE_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(EMPLOYEE_STATUSES)}")
        return v


class CompanyEmployeeCreate(CompanyEmployeeBase):
    """Schema for creating a new company employee."""
    pass


class CompanyEmployeeUpdate(BaseModel):
    """Schema for updating a company employee. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    date_of_joining: Optional[date] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

    @validator("status")
    def validate_status(cls, v):
        if v is not None and v not in EMPLOYEE_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(EMPLOYEE_STATUSES)}")
        return v


class CompanyEmployeeResponse(CompanyEmployeeBase):
    """Schema for company employee response."""

    id: UUID
    client_id: UUID
    candidate_id: Optional[UUID] = None
    application_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
