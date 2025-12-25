"""Tests for FSM service functionality."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from ats_backend.services.fsm_service import FSMService
from ats_backend.models.candidate import Candidate
from ats_backend.models.fsm_transition_log import FSMTransitionLog, ActorType


class TestFSMService:
    """Test FSM service functionality."""
    
    def test_valid_states_defined(self):
        """Test that valid states are properly defined."""
        assert FSMService.VALID_STATES == ["ACTIVE", "INACTIVE", "JOINED", "LEFT_COMPANY"]
        assert FSMService.TERMINAL_STATES == ["LEFT_COMPANY"]
    
    def test_transition_candidate_status_success(self):
        """Test successful candidate status transition."""
        # Setup
        mock_db = MagicMock()
        candidate_id = uuid4()
        actor_id = uuid4()
        
        # Mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_candidate.status = "ACTIVE"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        # Create service
        fsm_service = FSMService(mock_db)
        
        # Execute transition
        result = fsm_service.transition_candidate_status(
            candidate_id=candidate_id,
            new_status="JOINED",
            actor_id=actor_id,
            actor_type=ActorType.USER,
            reason="Employee joined the company"
        )
        
        # Verify
        assert result == mock_candidate
        assert mock_candidate.status == "JOINED"
        mock_db.commit.assert_called_once()
        mock_db.execute.assert_called()  # Session variables were set
    
    def test_transition_candidate_status_invalid_status(self):
        """Test transition with invalid status raises ValueError."""
        mock_db = MagicMock()
        fsm_service = FSMService(mock_db)
        
        with pytest.raises(ValueError, match="Invalid status: INVALID"):
            fsm_service.transition_candidate_status(
                candidate_id=uuid4(),
                new_status="INVALID",
                reason="Test"
            )
    
    def test_transition_candidate_not_found(self):
        """Test transition with non-existent candidate raises ValueError."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        fsm_service = FSMService(mock_db)
        candidate_id = uuid4()
        
        with pytest.raises(ValueError, match=f"Candidate with ID {candidate_id} not found"):
            fsm_service.transition_candidate_status(
                candidate_id=candidate_id,
                new_status="JOINED",
                reason="Test"
            )
    
    def test_transition_same_status_no_change(self):
        """Test transition to same status returns candidate without changes."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock candidate already in target status
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_candidate.status = "JOINED"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        fsm_service = FSMService(mock_db)
        
        result = fsm_service.transition_candidate_status(
            candidate_id=candidate_id,
            new_status="JOINED",
            reason="Test"
        )
        
        assert result == mock_candidate
        # Status should remain unchanged
        assert mock_candidate.status == "JOINED"
    
    def test_transition_rollback_on_error(self):
        """Test that database rollback occurs on error."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_candidate.status = "ACTIVE"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        # Mock commit to raise an exception (simulating database constraint violation)
        mock_db.commit.side_effect = IntegrityError("Constraint violation", None, None)
        
        fsm_service = FSMService(mock_db)
        
        with pytest.raises(IntegrityError):
            fsm_service.transition_candidate_status(
                candidate_id=candidate_id,
                new_status="LEFT_COMPANY",
                reason="Test"
            )
        
        # Verify rollback was called
        mock_db.rollback.assert_called_once()
    
    def test_can_transition_to_valid(self):
        """Test can_transition_to with valid transition."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock candidate in ACTIVE status
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_candidate.status = "ACTIVE"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        fsm_service = FSMService(mock_db)
        
        can_transition, reason = fsm_service.can_transition_to(candidate_id, "JOINED")
        
        assert can_transition is True
        assert reason == "Transition is allowed"
    
    def test_can_transition_to_invalid_status(self):
        """Test can_transition_to with invalid status."""
        mock_db = MagicMock()
        fsm_service = FSMService(mock_db)
        
        can_transition, reason = fsm_service.can_transition_to(uuid4(), "INVALID")
        
        assert can_transition is False
        assert "Invalid status: INVALID" in reason
    
    def test_can_transition_to_terminal_state(self):
        """Test can_transition_to from terminal state."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock candidate in terminal status
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_candidate.status = "LEFT_COMPANY"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        fsm_service = FSMService(mock_db)
        
        can_transition, reason = fsm_service.can_transition_to(candidate_id, "ACTIVE")
        
        assert can_transition is False
        assert "Cannot transition from terminal state LEFT_COMPANY" in reason
    
    def test_can_transition_to_left_company_without_joined(self):
        """Test can_transition_to LEFT_COMPANY without JOINED state."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock candidate in ACTIVE status
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_candidate.status = "ACTIVE"
        
        # Set up separate mock chains for different queries
        candidate_query_mock = MagicMock()
        candidate_query_mock.filter.return_value.first.return_value = mock_candidate
        
        transition_query_mock = MagicMock()
        transition_query_mock.filter.return_value.first.return_value = None  # No JOINED transition
        
        # Configure mock_db.query to return different mocks based on the model
        def query_side_effect(model):
            if model == Candidate:
                return candidate_query_mock
            else:  # FSMTransitionLog
                return transition_query_mock
        
        mock_db.query.side_effect = query_side_effect
        
        fsm_service = FSMService(mock_db)
        
        can_transition, reason = fsm_service.can_transition_to(candidate_id, "LEFT_COMPANY")
        
        assert can_transition is False
        assert "Cannot transition from ACTIVE to LEFT_COMPANY without first transitioning to JOINED" in reason
    
    def test_get_transition_history(self):
        """Test getting transition history for a candidate."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock transition logs
        mock_transitions = [
            MagicMock(spec=FSMTransitionLog),
            MagicMock(spec=FSMTransitionLog)
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_transitions
        
        fsm_service = FSMService(mock_db)
        
        result = fsm_service.get_transition_history(candidate_id, limit=50)
        
        assert result == mock_transitions
        mock_db.query.assert_called_with(FSMTransitionLog)
    
    def test_update_candidate_with_protection_success(self):
        """Test successful candidate update with protection."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        actor_id = uuid4()
        
        # Mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        fsm_service = FSMService(mock_db)
        
        updates = {"ctc_current": 50000.00, "ctc_expected": 60000.00}
        
        result = fsm_service.update_candidate_with_protection(
            candidate_id=candidate_id,
            updates=updates,
            actor_id=actor_id,
            actor_type=ActorType.USER
        )
        
        assert result == mock_candidate
        assert mock_candidate.ctc_current == 50000.00
        assert mock_candidate.ctc_expected == 60000.00
        mock_db.commit.assert_called_once()
    
    def test_update_candidate_with_protection_invalid_field(self):
        """Test candidate update with invalid field raises ValueError."""
        mock_db = MagicMock()
        candidate_id = uuid4()
        
        # Mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.id = candidate_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_candidate
        
        # Mock hasattr to return False for invalid field
        with patch('builtins.hasattr', return_value=False):
            fsm_service = FSMService(mock_db)
            
            with pytest.raises(ValueError, match="Invalid field: invalid_field"):
                fsm_service.update_candidate_with_protection(
                    candidate_id=candidate_id,
                    updates={"invalid_field": "value"}
                )
    
    def test_update_candidate_not_found(self):
        """Test update with non-existent candidate raises ValueError."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        fsm_service = FSMService(mock_db)
        candidate_id = uuid4()
        
        with pytest.raises(ValueError, match=f"Candidate with ID {candidate_id} not found"):
            fsm_service.update_candidate_with_protection(
                candidate_id=candidate_id,
                updates={"ctc_current": 50000.00}
            )