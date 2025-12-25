"""FSM service for managing candidate state transitions with invariant enforcement."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

from ats_backend.models.candidate import Candidate
from ats_backend.models.fsm_transition_log import FSMTransitionLog, ActorType

logger = structlog.get_logger(__name__)


class FSMService:
    """Service for managing FSM transitions with invariant enforcement."""
    
    VALID_STATES = ["ACTIVE", "INACTIVE", "JOINED", "LEFT_COMPANY"]
    TERMINAL_STATES = ["LEFT_COMPANY"]
    
    def __init__(self, db: Session):
        self.db = db
    
    def transition_candidate_status(
        self,
        candidate_id: UUID,
        new_status: str,
        actor_id: Optional[UUID] = None,
        actor_type: ActorType = ActorType.SYSTEM,
        reason: str = "Status transition",
        allow_protected_modifications: bool = False
    ) -> Candidate:
        """
        Transition a candidate to a new status with FSM invariant enforcement.
        
        Args:
            candidate_id: UUID of the candidate
            new_status: New status to transition to
            actor_id: UUID of the actor performing the transition (optional)
            actor_type: Type of actor (USER or SYSTEM)
            reason: Reason for the transition
            allow_protected_modifications: Whether to allow protected field modifications
            
        Returns:
            Updated candidate object
            
        Raises:
            ValueError: If the transition is invalid
            Exception: If database constraints are violated
        """
        if new_status not in self.VALID_STATES:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {self.VALID_STATES}")
        
        # Get the candidate
        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate with ID {candidate_id} not found")
        
        old_status = candidate.status
        
        # Check if already in the target status
        if old_status == new_status:
            logger.info(
                "Candidate already in target status",
                candidate_id=str(candidate_id),
                status=new_status
            )
            return candidate
        
        # Set session variables for database triggers
        try:
            # Set actor information for logging trigger
            if actor_id:
                self.db.execute(text("SELECT set_config('app.current_user_id', :actor_id, true)"), 
                               {"actor_id": str(actor_id)})
            
            self.db.execute(text("SELECT set_config('app.actor_type', :actor_type, true)"), 
                           {"actor_type": actor_type.value})
            
            self.db.execute(text("SELECT set_config('app.transition_reason', :reason, true)"), 
                           {"reason": reason})
            
            # Allow protected field modifications if needed (for system operations)
            if allow_protected_modifications:
                self.db.execute(text("SELECT set_config('app.allow_protected_field_modification', 'true', true)"))
            else:
                self.db.execute(text("SELECT set_config('app.allow_protected_field_modification', 'false', true)"))
            
            # Perform the status transition
            # The database triggers will handle:
            # - Validation of state transitions (prevent skipping JOINED)
            # - Terminal state enforcement (no transitions from LEFT_COMPANY)
            # - Automatic blacklisting when transitioning to LEFT_COMPANY
            # - Logging of the transition
            candidate.status = new_status
            
            self.db.commit()
            
            logger.info(
                "Candidate status transition completed",
                candidate_id=str(candidate_id),
                old_status=old_status,
                new_status=new_status,
                actor_id=str(actor_id) if actor_id else None,
                actor_type=actor_type.value,
                reason=reason
            )
            
            return candidate
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "Candidate status transition failed",
                candidate_id=str(candidate_id),
                old_status=old_status,
                new_status=new_status,
                error=str(e)
            )
            raise
        
        finally:
            # Clear session variables
            self.db.execute(text("SELECT set_config('app.current_user_id', NULL, true)"))
            self.db.execute(text("SELECT set_config('app.actor_type', NULL, true)"))
            self.db.execute(text("SELECT set_config('app.transition_reason', NULL, true)"))
            self.db.execute(text("SELECT set_config('app.allow_protected_field_modification', NULL, true)"))
    
    def get_transition_history(
        self,
        candidate_id: UUID,
        limit: int = 100
    ) -> list[FSMTransitionLog]:
        """
        Get the transition history for a candidate.
        
        Args:
            candidate_id: UUID of the candidate
            limit: Maximum number of transitions to return
            
        Returns:
            List of FSM transition logs ordered by creation time (newest first)
        """
        return (
            self.db.query(FSMTransitionLog)
            .filter(FSMTransitionLog.candidate_id == candidate_id)
            .order_by(FSMTransitionLog.created_at.desc())
            .limit(limit)
            .all()
        )
    
    def can_transition_to(self, candidate_id: UUID, target_status: str) -> tuple[bool, str]:
        """
        Check if a candidate can transition to a target status.
        
        Args:
            candidate_id: UUID of the candidate
            target_status: Target status to check
            
        Returns:
            Tuple of (can_transition, reason)
        """
        if target_status not in self.VALID_STATES:
            return False, f"Invalid status: {target_status}"
        
        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return False, f"Candidate with ID {candidate_id} not found"
        
        current_status = candidate.status
        
        # Check if already in target status
        if current_status == target_status:
            return False, f"Candidate is already in {target_status} status"
        
        # Check terminal state constraint
        if current_status in self.TERMINAL_STATES:
            return False, f"Cannot transition from terminal state {current_status}"
        
        # Check JOINED state requirement for LEFT_COMPANY
        if current_status == "ACTIVE" and target_status == "LEFT_COMPANY":
            # Check if candidate has ever been in JOINED state
            has_joined = (
                self.db.query(FSMTransitionLog)
                .filter(
                    FSMTransitionLog.candidate_id == candidate_id,
                    FSMTransitionLog.new_status == "JOINED"
                )
                .first()
            ) is not None
            
            if not has_joined:
                return False, "Cannot transition from ACTIVE to LEFT_COMPANY without first transitioning to JOINED"
        
        return True, "Transition is allowed"
    
    def update_candidate_with_protection(
        self,
        candidate_id: UUID,
        updates: dict,
        actor_id: Optional[UUID] = None,
        actor_type: ActorType = ActorType.SYSTEM,
        allow_protected_modifications: bool = False
    ) -> Candidate:
        """
        Update candidate fields with protection against unauthorized modifications.
        
        Args:
            candidate_id: UUID of the candidate
            updates: Dictionary of field updates
            actor_id: UUID of the actor performing the update (optional)
            actor_type: Type of actor (USER or SYSTEM)
            allow_protected_modifications: Whether to allow protected field modifications
            
        Returns:
            Updated candidate object
            
        Raises:
            ValueError: If the candidate is not found
            Exception: If protected field modifications are attempted without permission
        """
        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate with ID {candidate_id} not found")
        
        try:
            # Set session variables for database triggers
            if actor_id:
                self.db.execute(text("SELECT set_config('app.current_user_id', :actor_id, true)"), 
                               {"actor_id": str(actor_id)})
            
            self.db.execute(text("SELECT set_config('app.actor_type', :actor_type, true)"), 
                           {"actor_type": actor_type.value})
            
            if allow_protected_modifications:
                self.db.execute(text("SELECT set_config('app.allow_protected_field_modification', 'true', true)"))
            else:
                self.db.execute(text("SELECT set_config('app.allow_protected_field_modification', 'false', true)"))
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(candidate, field):
                    setattr(candidate, field, value)
                else:
                    raise ValueError(f"Invalid field: {field}")
            
            self.db.commit()
            
            logger.info(
                "Candidate updated with protection",
                candidate_id=str(candidate_id),
                updates=list(updates.keys()),
                actor_id=str(actor_id) if actor_id else None,
                actor_type=actor_type.value
            )
            
            return candidate
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "Candidate update failed",
                candidate_id=str(candidate_id),
                updates=list(updates.keys()),
                error=str(e)
            )
            raise
        
        finally:
            # Clear session variables
            self.db.execute(text("SELECT set_config('app.current_user_id', NULL, true)"))
            self.db.execute(text("SELECT set_config('app.actor_type', NULL, true)"))
            self.db.execute(text("SELECT set_config('app.allow_protected_field_modification', NULL, true)"))