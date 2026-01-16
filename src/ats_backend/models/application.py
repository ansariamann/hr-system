"""Application model linking candidates to jobs."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class Application(Base):
    """Application model representing candidate job applications."""
    
    __tablename__ = "applications"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    candidate_id = Column(GUID(), ForeignKey("candidates.id"), nullable=False)
    job_title = Column(String(255), nullable=True)
    application_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), default="RECEIVED", nullable=False)
    flagged_for_review = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    
    def __repr__(self) -> str:
        return f"<Application(id={self.id}, candidate_id={self.candidate_id}, client_id={self.client_id})>"
    
    @property
    def is_deleted(self) -> bool:
        """Check if application is soft deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Perform soft delete by setting deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()