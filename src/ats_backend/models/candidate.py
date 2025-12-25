"""Candidate model for job applicants."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, DECIMAL, Boolean, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base


class Candidate(Base):
    """Candidate model representing job applicants."""
    
    __tablename__ = "candidates"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(PG_UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    skills = Column(JSONB, nullable=True)
    experience = Column(JSONB, nullable=True)
    ctc_current = Column(DECIMAL(12, 2), nullable=True)
    ctc_expected = Column(DECIMAL(12, 2), nullable=True)
    status = Column(String(50), default="ACTIVE", nullable=False)
    is_blacklisted = Column(Boolean, default=False, nullable=False)
    candidate_hash = Column(String(64), nullable=True)
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