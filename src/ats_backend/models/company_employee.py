"""CompanyEmployee model for tracking employees in client companies."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class CompanyEmployee(Base):
    """Represents an employee within a client's company.

    Records are auto-created when a candidate is selected/hired,
    or manually created by client portal users.
    """

    __tablename__ = "company_employees"

    id = Column(GUID(), primary_key=True, default=uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False, index=True)
    candidate_id = Column(GUID(), ForeignKey("candidates.id"), nullable=True, index=True)
    application_id = Column(GUID(), ForeignKey("applications.id"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    role = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    date_of_joining = Column(Date, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE", server_default="ACTIVE")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="company_employees")
    candidate = relationship("Candidate", foreign_keys=[candidate_id])
    application = relationship("Application", foreign_keys=[application_id])

    def __repr__(self) -> str:
        return f"<CompanyEmployee(id={self.id}, name='{self.name}', role='{self.role}', client_id={self.client_id})>"
