"""Schemas for job postings."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    title: str = Field(..., max_length=255)
    company_name: str = Field(..., max_length=255)
    posting_date: Optional[date] = None
    requirements: Optional[str] = None
    experience_required: Optional[int] = Field(default=None, ge=0, le=60)
    salary_lpa: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = None


class JobCreate(JobBase):
    client_id: Optional[UUID] = None


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    company_name: Optional[str] = Field(default=None, max_length=255)
    posting_date: Optional[date] = None
    requirements: Optional[str] = None
    experience_required: Optional[int] = Field(default=None, ge=0, le=60)
    salary_lpa: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = None


class JobResponse(JobBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
