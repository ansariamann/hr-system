"""Schemas for job postings."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    title: str = Field(..., max_length=255)
    company_name: Optional[str] = Field(default=None, max_length=255)
    posting_date: Optional[date] = None
    closing_date: Optional[date] = None
    requirements: Optional[str] = None
    department: Optional[str] = Field(default=None, max_length=255)
    employment_type: str = Field(default="FULL_TIME", max_length=50)
    experience_required: Optional[int] = Field(default=None, ge=0, le=60)
    salary_lpa: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = None
    openings_count: int = Field(default=1, ge=1, le=1000)
    status: str = Field(default="OPEN", max_length=50)


class JobCreate(JobBase):
    client_id: Optional[UUID] = None


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    company_name: Optional[str] = Field(default=None, max_length=255)
    posting_date: Optional[date] = None
    closing_date: Optional[date] = None
    requirements: Optional[str] = None
    department: Optional[str] = Field(default=None, max_length=255)
    employment_type: Optional[str] = Field(default=None, max_length=50)
    experience_required: Optional[int] = Field(default=None, ge=0, le=60)
    salary_lpa: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = None
    openings_count: Optional[int] = Field(default=None, ge=1, le=1000)
    status: Optional[str] = Field(default=None, max_length=50)


class JobResponse(JobBase):
    id: UUID
    client_id: UUID
    vacant: bool
    submitted_by_client: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
