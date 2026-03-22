"""Activity Log model for tracking application, candidate, and interview events."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class ActivityLog(Base):
    """Activity Log model tracking important application and candidate events."""
    
    __tablename__ = "activity_logs"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    action_type = Column(String(50), nullable=False) # e.g. 'APPLICATION_CREATED', 'CANDIDATE_UPLOADED', 'DIRECT_INTERVIEW'
    entity_id = Column(GUID(), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Optional relationships to help with joining if needed later
    client = relationship("Client")
    user = relationship("User")
    
    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, action_type='{self.action_type}', entity_id={self.entity_id}, created_at={self.created_at})>"
