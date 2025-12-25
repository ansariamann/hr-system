"""Simple tests for authentication middleware."""

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from ats_backend.auth.middleware import AuthenticationMiddleware
from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.auth.utils import create_access_token


# Create a simple test app
app = FastAPI()
app.add_middleware(AuthenticationMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/protected")
async def protected(current_user: User = Depends(get_current_user)):
    return {"user_id": str(current_user.id)}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Initialize database and Redis for tests."""
    import os
    import asyncio
    os.environ["TESTING"] = "true"
    
    # Override database settings for local testing
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PASSWORD"] = "ats_dev_password_2024"
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["TOKEN_REPLAY_PROTECTION"] = "false"  # Disable for tests
    
    from ats_backend.core.database import db_manager
    
    # Initialize database
    db_manager.initialize()
    
    yield
    
    # Clean up environment
    os.environ.pop("TESTING", None)
    os.environ.pop("TOKEN_REPLAY_PROTECTION", None)


def test_health_endpoint_no_auth(client):
    """Test that health endpoint works without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_no_auth(client):
    """Test protected endpoint without authentication."""
    response = client.get("/protected")
    assert response.status_code == 401


def test_protected_endpoint_invalid_token(client):
    """Test protected endpoint with invalid token."""
    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


@patch('ats_backend.auth.dependencies.get_user_by_id')
@patch('ats_backend.auth.dependencies.get_db')
@patch('ats_backend.auth.dependencies.set_client_context')
def test_protected_endpoint_valid_token(mock_set_context, mock_get_db, mock_get_user, client):
    """Test protected endpoint with valid token."""
    from uuid import uuid4
    
    # Mock user
    user_id = uuid4()
    client_id = uuid4()
    mock_user = Mock()
    mock_user.id = user_id
    mock_user.client_id = client_id
    mock_user.is_active = True
    
    # Mock database session
    mock_db = Mock()
    mock_get_db.return_value = iter([mock_db])
    mock_get_user.return_value = mock_user
    
    # Create valid token
    token_data = {
        "sub": str(user_id),
        "client_id": str(client_id),
        "email": "test@example.com"
    }
    token = create_access_token(token_data)
    
    # Make request with valid token
    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["user_id"] == str(user_id)
    
    # Verify that client context was set (check if it was called, not exact mock object)
    mock_set_context.assert_called_once()
    call_args = mock_set_context.call_args
    assert call_args[0][1] == client_id  # Check client_id argument


def test_middleware_skips_auth_paths(client):
    """Test that middleware skips authentication for certain paths."""
    # These should all work without authentication
    skip_paths = ["/health"]
    
    for path in skip_paths:
        response = client.get(path)
        # Should not get 401 (authentication required)
        assert response.status_code != 401