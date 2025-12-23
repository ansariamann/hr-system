"""Authentication utilities."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.config import settings
from .models import User, TokenData

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    
    logger.debug("Access token created", expires_at=expire.isoformat())
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        
        user_id_str: str = payload.get("sub")
        client_id_str: str = payload.get("client_id")
        email: str = payload.get("email")
        
        if user_id_str is None:
            logger.warning("Token missing user ID")
            return None
            
        user_id = UUID(user_id_str)
        client_id = UUID(client_id_str) if client_id_str else None
        
        token_data = TokenData(
            user_id=user_id,
            client_id=client_id,
            email=email
        )
        
        logger.debug("Token verified successfully", user_id=str(user_id))
        return token_data
        
    except JWTError as e:
        logger.warning("Token verification failed", error=str(e))
        return None
    except ValueError as e:
        logger.warning("Invalid UUID in token", error=str(e))
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        User if authentication successful, None otherwise
    """
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        logger.warning("User not found", email=email)
        return None
        
    if not user.is_active:
        logger.warning("User is inactive", email=email)
        return None
        
    if not verify_password(password, user.hashed_password):
        logger.warning("Invalid password", email=email)
        return None
        
    logger.info("User authenticated successfully", email=email, user_id=str(user.id))
    return user


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    """Get user by ID.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email.
    
    Args:
        db: Database session
        email: User email
        
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.email == email, User.is_active == True).first()


def create_user(db: Session, user_create: dict) -> User:
    """Create a new user.
    
    Args:
        db: Database session
        user_create: User creation data
        
    Returns:
        Created user
    """
    hashed_password = get_password_hash(user_create["password"])
    
    db_user = User(
        email=user_create["email"],
        hashed_password=hashed_password,
        full_name=user_create.get("full_name"),
        client_id=user_create["client_id"],
        is_active=user_create.get("is_active", True)
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info("User created", email=user_create["email"], user_id=str(db_user.id))
    return db_user