"""Unit tests for session context management."""

import sys
from unittest.mock import MagicMock

# Mock missing dependencies
mock_sqlalchemy = MagicMock()
mock_structlog = MagicMock()

sys.modules['sqlalchemy'] = mock_sqlalchemy
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.orm'].Session = MagicMock()
sys.modules['sqlalchemy.sql'] = MagicMock()
sys.modules['sqlalchemy.sql.expression'] = MagicMock()
sys.modules['structlog'] = mock_structlog

# Define a simple text mock that returns its input when stringified
class MockText:
    def __init__(self, text):
        self.text = text
    def __str__(self):
        return self.text

mock_sqlalchemy.text = MockText

import pytest
from unittest.mock import patch
from uuid import UUID, uuid4

# Now we can import the code under test
from ats_backend.core.session_context import (
    SessionContextManager,
    set_client_context,
    clear_client_context,
    get_current_client_id,
    with_client_context
)

class TestSessionContextManager:
    """Tests for SessionContextManager static methods."""

    def test_set_client_context_success(self):
        """Test successful setting of client context."""
        session = MagicMock()
        client_id = uuid4()

        SessionContextManager.set_client_context(session, client_id)

        # Verify execute was called with correct SQL and parameters
        args, _ = session.execute.call_args
        assert str(args[0]) == "SET LOCAL app.current_client_id = :client_id"
        assert args[1] == {"client_id": str(client_id)}

    def test_set_client_context_none_id(self):
        """Test that None client_id raises ValueError."""
        session = MagicMock()
        with pytest.raises(ValueError, match="Client ID cannot be None"):
            SessionContextManager.set_client_context(session, None)

    def test_set_client_context_error(self):
        """Test that database errors are propagated."""
        session = MagicMock()
        session.execute.side_effect = Exception("DB Error")
        client_id = uuid4()

        with pytest.raises(Exception, match="DB Error"):
            SessionContextManager.set_client_context(session, client_id)

    def test_clear_client_context_success(self):
        """Test successful clearing of client context."""
        session = MagicMock()

        SessionContextManager.clear_client_context(session)

        # Verify execute was called with correct SQL
        args, _ = session.execute.call_args
        assert str(args[0]) == "SET LOCAL app.current_client_id = ''"

    def test_clear_client_context_error(self):
        """Test that database errors during clear are propagated."""
        session = MagicMock()
        session.execute.side_effect = Exception("DB Error")

        with pytest.raises(Exception, match="DB Error"):
            SessionContextManager.clear_client_context(session)

    def test_get_current_client_id_success(self):
        """Test successful retrieval of current client ID."""
        session = MagicMock()
        client_id = uuid4()
        session.execute.return_value.scalar.return_value = str(client_id)

        result = SessionContextManager.get_current_client_id(session)

        assert result == client_id
        # Verify execute call
        args, _ = session.execute.call_args
        assert str(args[0]) == "SELECT current_setting('app.current_client_id', true)"

    def test_get_current_client_id_empty(self):
        """Test retrieval when context is empty or None."""
        session = MagicMock()

        # Test None return
        session.execute.return_value.scalar.return_value = None
        assert SessionContextManager.get_current_client_id(session) is None

        # Test empty string return
        session.execute.return_value.scalar.return_value = ""
        assert SessionContextManager.get_current_client_id(session) is None

    def test_get_current_client_id_whitespace(self):
        """Test retrieval when context contains only whitespace."""
        session = MagicMock()
        session.execute.return_value.scalar.return_value = "   "

        assert SessionContextManager.get_current_client_id(session) is None

    def test_get_current_client_id_error(self):
        """Test that errors during get return None."""
        session = MagicMock()
        session.execute.side_effect = Exception("DB Error")

        result = SessionContextManager.get_current_client_id(session)
        assert result is None

    def test_with_client_context_restores_original(self):
        """Test that original context is restored after the block."""
        session = MagicMock()
        original_id = uuid4()
        new_id = uuid4()

        # Setup mocks to return original_id first
        with patch.object(SessionContextManager, 'get_current_client_id', return_value=original_id), \
             patch.object(SessionContextManager, 'set_client_context') as mock_set:

            with SessionContextManager.with_client_context(session, new_id):
                mock_set.assert_called_once_with(session, new_id)
                mock_set.reset_mock()

            # Verify restoration
            mock_set.assert_called_once_with(session, original_id)

    def test_with_client_context_clears_if_no_original(self):
        """Test that context is cleared if no original existed."""
        session = MagicMock()
        new_id = uuid4()

        with patch.object(SessionContextManager, 'get_current_client_id', return_value=None), \
             patch.object(SessionContextManager, 'set_client_context') as mock_set, \
             patch.object(SessionContextManager, 'clear_client_context') as mock_clear:

            with SessionContextManager.with_client_context(session, new_id):
                mock_set.assert_called_once_with(session, new_id)

            # Verify clearing
            mock_clear.assert_called_once_with(session)

class TestConvenienceFunctions:
    """Tests for top-level convenience functions."""

    def test_set_client_context_delegation(self):
        """Test that top-level set_client_context delegates correctly."""
        session = MagicMock()
        client_id = uuid4()
        with patch.object(SessionContextManager, 'set_client_context') as mock_method:
            set_client_context(session, client_id)
            mock_method.assert_called_once_with(session, client_id)

    def test_clear_client_context_delegation(self):
        """Test that top-level clear_client_context delegates correctly."""
        session = MagicMock()
        with patch.object(SessionContextManager, 'clear_client_context') as mock_method:
            clear_client_context(session)
            mock_method.assert_called_once_with(session)

    def test_get_current_client_id_delegation(self):
        """Test that top-level get_current_client_id delegates correctly."""
        session = MagicMock()
        expected_id = uuid4()
        with patch.object(SessionContextManager, 'get_current_client_id', return_value=expected_id) as mock_method:
            result = get_current_client_id(session)
            assert result == expected_id
            mock_method.assert_called_once_with(session)

    def test_with_client_context_delegation(self):
        """Test that top-level with_client_context delegates correctly."""
        session = MagicMock()
        client_id = uuid4()

        # SessionContextManager.with_client_context is a context manager
        # we need to mock it as such
        with patch.object(SessionContextManager, 'with_client_context') as mock_manager:
            # Setup the mock to be a context manager
            mock_manager.return_value.__enter__.return_value = session

            with with_client_context(session, client_id) as ctx_session:
                assert ctx_session == session

            mock_manager.assert_called_once_with(session, client_id)
