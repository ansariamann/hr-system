"""Resume job model for tracking processing tasks."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base


class ResumeJob(Base):
    """Resume job model for tracking resume processing tasks."""
    
    __tablename__ = "resume_jobs"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(PG_UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    email_message_id = Column(String(255), unique=True, nullable=True)  # For deduplication
    file_name = Column(String(255), nullable=True)
    file_path = Column(Text, nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="resume_jobs")
    
    def __repr__(self) -> str:
        return f"<ResumeJob(id={self.id}, status='{self.status}', client_id={self.client_id})>"
    
    def mark_processed(self) -> None:
        """Mark job as processed with timestamp."""
        self.status = "COMPLETED"
        self.processed_at = datetime.utcnow()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed with error message."""
        self.status = "FAILED"
        self.error_message = error_message
        self.processed_at = datetime.utcnow()