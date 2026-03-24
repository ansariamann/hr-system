"""Interview Record model for direct interviews."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class InterviewRecord(Base):
    """Interview Record model for tracking direct interviews with candidates."""
    
    __tablename__ = "interview_records"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    candidate_id = Column(GUID(), ForeignKey("candidates.id"), nullable=False)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    company_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    interviewer_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    interview_date = Column(DateTime, nullable=False)
    position = Column(String(255), nullable=True)
    skills = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # 1-5 scale
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete for audit trail
    
    # Relationships
    candidate = relationship("Candidate", foreign_keys=[candidate_id])
    client = relationship("Client", foreign_keys=[client_id])
    company = relationship("Client", foreign_keys=[company_id])
    interviewer = relationship("User", foreign_keys=[interviewer_id])
    
    def __repr__(self) -> str:
        return f"<InterviewRecord(id={self.id}, candidate_id={self.candidate_id}, company_id={self.company_id})>"
