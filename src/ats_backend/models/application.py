"""Application model linking candidates to jobs."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class Application(Base):
    """Application model representing candidate job applications."""
    
    __tablename__ = "applications"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    candidate_id = Column(GUID(), ForeignKey("candidates.id"), nullable=False)
    job_id = Column(GUID(), ForeignKey("jobs.id"), nullable=True)
    job_title = Column(String(255), nullable=True)
    application_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String(100), nullable=False, default="MANUAL", server_default="MANUAL")
    status = Column(String(50), default="RECEIVED", nullable=False)
    status_updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    flagged_for_review = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    applied_by_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    hr_interview_acknowledged = Column(Boolean, default=False, nullable=False, server_default="false")
    hr_interview_acknowledged_at = Column(DateTime, nullable=True)
    hr_interview_acknowledged_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    hr_interview_ack_note = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    applied_by_user = relationship("User", foreign_keys=[applied_by_user_id])
    hr_interview_acknowledged_user = relationship("User", foreign_keys=[hr_interview_acknowledged_by])
    
    def __repr__(self) -> str:
        return f"<Application(id={self.id}, candidate_id={self.candidate_id}, client_id={self.client_id})>"
    
    @property
    def is_deleted(self) -> bool:
        """Check if application is soft deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self) -> None:
        """Perform soft delete by setting deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()
