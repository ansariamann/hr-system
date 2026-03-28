"""Job model for job postings."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    closing_date = Column(Date, nullable=True)
    requirements = Column(Text, nullable=True)
    department = Column(String(255), nullable=True, index=True)
    employment_type = Column(String(50), nullable=False, default="FULL_TIME", server_default="FULL_TIME")
    experience_required = Column(Integer, nullable=True)
    salary_lpa = Column(Numeric(10, 2), nullable=True)
    location = Column(String(255), nullable=True, index=True)
    openings_count = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(String(50), nullable=False, default="OPEN", server_default="OPEN", index=True)
    submitted_by_client = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    client = relationship("Client", back_populates="jobs")
    applications = relationship("Application", back_populates="job")
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company_name}')>"
