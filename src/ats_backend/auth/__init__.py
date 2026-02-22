"""Authentication and authorization module."""

from .middleware import AuthenticationMiddleware
from .decorators import require_auth, require_client_access
from .dependencies import get_current_client, get_current_user, require_roles
from .models import (
    User,
    UserCreate,
    UserResponse,
    Token,
    RegisterRequest,
    RegisterResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    RoleValidationRequest,
    RoleValidationResponse,
)
from .utils import (
    create_access_token,
    verify_token,
    get_password_hash,
    verify_password,
    normalize_role,
)

__all__ = [
    "AuthenticationMiddleware",
    "require_auth",
    "require_client_access", 
    "get_current_client",
    "get_current_user",
    "require_roles",
    "User",
    "UserCreate",
    "UserResponse",
    "Token",
    "RegisterRequest",
    "RegisterResponse",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "RoleValidationRequest",
    "RoleValidationResponse",
    "create_access_token",
    "verify_token",
    "get_password_hash",
    "verify_password",
    "normalize_role",
]
