"""Authentication and authorization module."""

from .middleware import AuthenticationMiddleware
from .decorators import require_auth, require_client_access
from .dependencies import get_current_client, get_current_user
from .models import User, UserCreate, UserResponse, Token
from .utils import create_access_token, verify_token, get_password_hash, verify_password

__all__ = [
    "AuthenticationMiddleware",
    "require_auth",
    "require_client_access", 
    "get_current_client",
    "get_current_user",
    "User",
    "UserCreate",
    "UserResponse",
    "Token",
    "create_access_token",
    "verify_token",
    "get_password_hash",
    "verify_password",
]