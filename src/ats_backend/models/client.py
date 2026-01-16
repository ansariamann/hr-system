"""Client model for multi-tenant organizations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class Client(Base):
    """Client model representing tenant organizations."""
    
    __tablename__ = "clients"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    email_domain = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    candidates = relationship("Candidate", back_populates="client", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="client", cascade="all, delete-orphan")
    resume_jobs = relationship("ResumeJob", back_populates="client", cascade="all, delete-orphan")
    users = relationship("User", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name='{self.name}')>"