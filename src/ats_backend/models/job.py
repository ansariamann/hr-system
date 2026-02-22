"""Job model for job postings."""

from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Date, Integer, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class Job(Base):
    """Job posting model."""
    
    __tablename__ = "jobs"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    posting_date = Column(Date, nullable=False, default=date.today)
    requirements = Column(Text, nullable=True)
    experience_required = Column(Integer, nullable=True)
    salary_lpa = Column(Numeric(10, 2), nullable=True)
    location = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    client = relationship("Client", back_populates="jobs")
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company_name}')>"
