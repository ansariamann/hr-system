"""Tests for authentication and multi-tenant middleware."""

import pytest
from datetime import timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ats_backend.core.base import Base
from ats_backend.core.database import get_db
from ats_backend.main import app
from ats_backend.models.client import Client
from ats_backend.auth.models import User
from ats_backend.auth.utils import get_password_hash, create_access_token
from ats_backend.services.client_service import ClientService

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    """Set up test database."""
    # Monkey patch JSONB to JSON for SQLite compatibility
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB
    original_jsonb = JSONB
    import sqlalchemy.dialects.postgresql
    sqlalchemy.dialects.postgresql.JSONB = JSON
    
    # Also patch the models directly before creating tables
    from ats_backend.models.candidate import Candidate
    from ats_backend.core.audit import AuditLog
    
    # Store original column types
    original_skills = Candidate.__table__.columns['skills'].type
    original_experience = Candidate.__table__.columns['experience'].type
    original_old_values = AuditLog.__table__.columns['old_values'].type
    original_new_values = AuditLog.__table__.columns['new_values'].type
    original_changes = AuditLog.__table__.columns['changes'].type
    
    try:
        # Replace JSONB columns with JSON
        Candidate.__table__.columns['skills'].type = JSON()
        Candidate.__table__.columns['experience'].type = JSON()
        AuditLog.__table__.columns['old_values'].type = JSON()
        AuditLog.__table__.columns['new_values'].type = JSON()
        AuditLog.__table__.columns['changes'].type = JSON()
        
        Base.metadata.create_all(bind=engine)
        yield
        Base.metadata.drop_all(bind=engine)
    finally:
        # Restore original types
        Candidate.__table__.columns['skills'].type = original_skills
        Candidate.__table__.columns['experience'].type = original_experience
        AuditLog.__table__.columns['old_values'].type = original_old_values
        AuditLog.__table__.columns['new_values'].type = original_new_values
        AuditLog.__table__.columns['changes'].type = original_changes
        # Restore original JSONB
        sqlalchemy.dialects.postgresql.JSONB = original_jsonb


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_client_data(setup_database):
    """Create test client and user."""
    db = TestingSessionLocal()
    
    try:
        # Create test client
        client = ClientService.create_client(
            db=db,
            name="Test Company",
            email_domain="test.com"
        )
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == "test@test.com").first()
        if existing_user:
            # Delete existing user to avoid conflicts
            db.delete(existing_user)
            db.commit()
        
        # Create test user with shorter password to avoid bcrypt 72-byte limit
        user = User(
            email="test@test.com",
            hashed_password=get_password_hash("testpass"),  # Shorter password
            full_name="Test User",
            client_id=client.id,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        yield {"client": client, "user": user}
    finally:
        db.close()


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "ats-backend"}


def test_login_success(client, test_client_data):
    """Test successful login."""
    response = client.post(
        "/auth/login",
        data={
            "username": "test@test.com",
            "password": "testpass"  # Match the shorter password
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


def test_login_invalid_credentials(client, test_client_data):
    """Test login with invalid credentials."""
    response = client.post(
        "/auth/login",
        data={
            "username": "test@test.com",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_protected_endpoint_without_auth(client):
    """Test protected endpoint without authentication."""
    response = client.get("/protected")
    assert response.status_code == 401


def test_protected_endpoint_with_auth(client, test_client_data):
    """Test protected endpoint with authentication."""
    # First login to get token
    login_response = client.post(
        "/auth/login",
        data={
            "username": "test@test.com",
            "password": "testpass"  # Match the shorter password
        }
    )
    
    token = login_response.json()["access_token"]
    
    # Use token to access protected endpoint
    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "user_id" in data
    assert "client_id" in data


def test_get_current_user_info(client, test_client_data):
    """Test getting current user information."""
    # Login to get token
    login_response = client.post(
        "/auth/login",
        data={
            "username": "test@test.com",
            "password": "testpass"  # Match the shorter password
        }
    )
    
    token = login_response.json()["access_token"]
    
    # Get user info
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@test.com"
    assert data["full_name"] == "Test User"
    assert data["is_active"] == True


def test_get_current_client_info(client, test_client_data):
    """Test getting current client information."""
    # Login to get token
    login_response = client.post(
        "/auth/login",
        data={
            "username": "test@test.com",
            "password": "testpass"  # Match the shorter password
        }
    )
    
    token = login_response.json()["access_token"]
    
    # Get client info
    response = client.get(
        "/auth/client",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Company"
    assert data["email_domain"] == "test.com"


def test_invalid_token(client):
    """Test with invalid token."""
    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401


def test_expired_token(client, test_client_data):
    """Test with expired token."""
    # Create expired token
    expired_token = create_access_token(
        data={"sub": str(test_client_data["user"].id)},
        expires_delta=timedelta(seconds=-1)  # Already expired
    )
    
    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    assert response.status_code == 401