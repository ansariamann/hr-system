"""Candidate model for job applicants."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, DECIMAL, Boolean, text, JSON, Text
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class Candidate(Base):
    """Candidate model representing job applicants."""
    
    __tablename__ = "candidates"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    skills = Column(JSON, nullable=True)
    experience = Column(JSON, nullable=True)
    ctc_current = Column(DECIMAL(12, 2), nullable=True)
    ctc_expected = Column(DECIMAL(12, 2), nullable=True)
    status = Column(String(50), default="ACTIVE", nullable=False)
    is_blacklisted = Column(Boolean, default=False, nullable=False)
    candidate_hash = Column(String(64), nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="candidates")
    applications = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, name='{self.name}', client_id={self.client_id})>"
    
    def generate_hash(self) -> str:
        """Generate candidate hash for duplicate detection."""
        # This will be handled by a database trigger using the generate_candidate_hash function
        return ""