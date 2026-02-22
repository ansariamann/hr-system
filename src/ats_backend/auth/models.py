"""Authentication models and schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship

from ats_backend.core.base import Base
from ats_backend.core.custom_types import GUID


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(String(50), default="client_user", nullable=False)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="users")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"

    @property
    def client_name(self) -> str:
        return self.client.name if self.client else "Unknown Client"


class PasswordResetToken(Base):
    """Password reset token model."""
    
    __tablename__ = "password_reset_tokens"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    requested_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User")
    
    def __repr__(self) -> str:
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


# Pydantic models for API
class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    role: str = "client_user"


class UserCreate(UserBase):
    """User creation schema."""
    password: str
    client_id: UUID


class UserResponse(UserBase):
    """User response schema."""
    id: UUID
    client_id: UUID
    role: str
    client_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token data schema for JWT payload."""
    user_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    email: Optional[str] = None
    role: Optional[str] = None


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    client_id: Optional[UUID] = None
    role: Optional[str] = None


class RegisterResponse(BaseModel):
    """User registration response."""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordResetRequest(BaseModel):
    """Password reset request (start)."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str


class RoleValidationRequest(BaseModel):
    """Role validation request."""
    roles: List[str]
    require_all: bool = False


class RoleValidationResponse(BaseModel):
    """Role validation response."""
    allowed: bool
    role: Optional[str] = None
    missing_roles: Optional[List[str]] = None
