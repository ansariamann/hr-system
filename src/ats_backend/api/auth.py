"""Authentication API endpoints."""

import logging
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ats_backend.core.config import settings
from ats_backend.core.database import get_db
from ats_backend.core.error_handling import with_error_handling
from ats_backend.core.session_context import set_client_context
from ats_backend.services.client_service import ClientService
from ats_backend.auth.dependencies import get_current_user, get_optional_current_user
from ats_backend.auth.models import (
    User,
    UserResponse,
    Token,
    RegisterRequest,
    RegisterResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetToken,
    RoleValidationRequest,
    RoleValidationResponse,
)
from ats_backend.auth.utils import (
    create_access_token,
    create_user,
    get_password_hash,
    normalize_role,
)
from ats_backend.email.send import send_email
from ats_backend.email.templates import render_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_email_domain(email: str) -> str:
    parts = email.split("@")
    if len(parts) != 2 or not parts[1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address"
        )
    return parts[1].lower()


def _can_assign_role(
    current_user: Optional[User],
    target_client_id,
    role: str
) -> bool:
    if current_user is None:
        return role == "client_user"
    
    acting_role = (current_user.role or "").lower()
    if acting_role == "hr_admin":
        return True
    if acting_role == "client_admin":
        if target_client_id != current_user.client_id:
            return False
        return role in {"client_user", "client_admin"}
    return False


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@with_error_handling(component="authentication")
def register_user(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Register a new user for a client."""
    email = payload.email.lower().strip()
    try:
        role = normalize_role(payload.role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    if payload.client_id and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id is not allowed without authentication"
        )
    
    if current_user:
        client_id = payload.client_id or current_user.client_id
        client = ClientService.get_client_by_id(db, client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
    else:
        domain = _extract_email_domain(email)
        client = ClientService.get_client_by_email_domain(db, domain)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No client matches this email domain"
            )
        client_id = client.id
    
    if not _can_assign_role(current_user, client_id, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to assign this role"
        )
    
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Set RLS context when creating the user
    set_client_context(db, client_id)
    
    user = create_user(
        db,
        {
            "email": email,
            "password": payload.password,
            "full_name": payload.full_name,
            "client_id": client_id,
            "role": role,
            "is_active": True,
        }
    )
    
    db.commit()
    db.refresh(user)
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "client_id": str(user.client_id),
            "email": user.email,
            "role": user.role,
        },
        expires_delta=access_token_expires
    )
    
    return RegisterResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/password/forgot")
@router.post("/forgot-password")
@with_error_handling(component="authentication")
def start_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Start password reset flow."""
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    
    # Always return success to avoid user enumeration
    if not user:
        return {"status": "ok"}
    
    set_client_context(db, user.client_id)
    
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.password_reset_token_minutes)
    
    reset_entry = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        requested_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(reset_entry)
    db.commit()
    
    # Determine reset link based on user role
    role = (user.role or "").lower()
    if role.startswith("hr_"):
        base_url = settings.frontend_hr_url.rstrip("/")
    else:
        base_url = settings.frontend_client_url.rstrip("/")
    reset_link = f"{base_url}/reset-password?token={token}"
    
    # Render and send the password reset email
    user_name = user.full_name or user.email
    html_body = render_password_reset_email(
        user_name=user_name,
        reset_link=reset_link,
        expiry_minutes=settings.password_reset_token_minutes,
    )
    send_email(
        to=user.email,
        subject="Reset Your Password",
        html_body=html_body,
    )
    
    response = {
        "status": "ok",
        "expires_in": settings.password_reset_token_minutes * 60
    }
    if settings.environment != "production":
        response["reset_token"] = token
    
    return response


@router.post("/password/reset")
@router.post("/reset-password")
@with_error_handling(component="authentication")
def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Confirm password reset using a token."""
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    reset_entry = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()
    
    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    if reset_entry.used_at is not None or reset_entry.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    user = db.query(User).filter(User.id == reset_entry.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or inactive"
        )
    
    set_client_context(db, user.client_id)
    user.hashed_password = get_password_hash(payload.new_password)
    reset_entry.used_at = datetime.utcnow()
    
    db.commit()
    
    return {"status": "ok"}


@router.post("/token/refresh", response_model=Token)
@with_error_handling(component="authentication")
def refresh_token(
    current_user: User = Depends(get_current_user)
):
    """Refresh access token for authenticated user."""
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "client_id": str(current_user.client_id),
            "email": current_user.email,
            "role": current_user.role,
        },
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/validate-role", response_model=RoleValidationResponse)
@with_error_handling(component="authentication")
def validate_role(
    payload: RoleValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate that current user has required role(s)."""
    required_roles = {role.strip().lower() for role in payload.roles}
    user_role = (current_user.role or "").strip().lower()
    
    if payload.require_all:
        allowed = required_roles.issubset({user_role})
    else:
        allowed = user_role in required_roles
    
    missing = None
    if not allowed:
        missing = sorted(list(required_roles - {user_role}))
    
    return RoleValidationResponse(
        allowed=allowed,
        role=user_role,
        missing_roles=missing
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@with_error_handling(component="authentication")
def logout_user():
    """Logout endpoint for compatibility (JWT is stateless)."""
    return None
