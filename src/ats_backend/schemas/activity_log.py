"""Activity Log schemas."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ActivityLogBase(BaseModel):
    """Base activity log schema."""
    action_type: str
    entity_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None


class ActivityLogCreate(ActivityLogBase):
    """Schema for creating an activity log."""
    pass


class ActivityLogResponse(ActivityLogBase):
    """Schema for activity log responses."""
    id: UUID
    client_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    created_at: datetime
    
    # For UI display
    user_name: Optional[str] = None

    class Config:
        """Pydantic config."""
        from_attributes = True
