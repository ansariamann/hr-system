"""FSM transition log model for tracking candidate state changes."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base


class ActorType(str, Enum):
    """Actor types for FSM transitions."""
    USER = "USER"
    SYSTEM = "SYSTEM"


class FSMTransitionLog(Base):
    """FSM transition log model for tracking candidate state changes."""
    
    __tablename__ = "fsm_transition_logs"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id = Column(PG_UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    old_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    actor_id = Column(PG_UUID(as_uuid=True), nullable=True)  # May be null for system actions
    actor_type = Column(String(20), default=ActorType.SYSTEM, nullable=False)
    reason = Column(Text, nullable=False)
    is_terminal = Column(Boolean, default=False, nullable=False)
    client_id = Column(PG_UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    candidate = relationship("Candidate", backref="fsm_transitions")
    client = relationship("Client", backref="fsm_transitions")
    
    def __repr__(self) -> str:
        return f"<FSMTransitionLog(id={self.id}, candidate_id={self.candidate_id}, {self.old_status}->{self.new_status})>"
    
    @property
    def transition_description(self) -> str:
        """Get a human-readable description of the transition."""
        return f"{self.old_status} → {self.new_status}"