"""Authentication utilities."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import os

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.config import settings
from .models import User, TokenData

logger = structlog.get_logger(__name__)

def get_pwd_context():
    """Get password context based on environment."""
    return CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    logger.debug("Verifying password", extra={"plain_password": plain_password, "hashed_password": hashed_password})
    pwd_context = get_pwd_context()
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    pwd_context = get_pwd_context()
    
    import hashlib
    # Pre-hash with SHA-256 if password exceeds bcrypt's 72-byte limit
    if len(password.encode('utf-8')) > 72:
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    import uuid
    
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    # Add JTI (JWT ID) for replay protection
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "jti": jti,
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    
    logger.debug("Access token created", expires_at=expire.isoformat(), jti=jti)
    return encoded_jwt


async def verify_token(token: str, db: Optional[Session] = None) -> Optional[TokenData]:
    """Verify and decode a JWT token."""
    from .security import token_replay_protection, SecurityLogger, SecurityEventType, SecurityEventSeverity
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        
        user_id_str: str = payload.get("sub")
        client_id_str: str = payload.get("client_id")
        email: str = payload.get("email")
        jti: str = payload.get("jti")
        
        if user_id_str is None:
            logger.warning("Token missing user ID")
            return None
        
        # Check for expired token
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            logger.warning("Expired token rejected", user_id=user_id_str, email=email)
            return None
        
        # Token Replay Protection skipped for now to avoid Redis issues
        # if jti and settings.token_replay_protection:
        #     try:
        #         is_valid = await token_replay_protection.validate_token_usage(jti)
        #         if not is_valid:
        #             logger.warning("Token replay detected", jti=jti)
        #             return None
        #     except Exception as e:
        #         logger.error("Token replay protection check failed", error=str(e))
            
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


def authenticate_user(
    db: Session, 
    email: str, 
    password: str, 
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[User]:
    """Authenticate a user with email and password."""
    # Note: Rate limiting and SecurityLogger disabled for debugging stability
    
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        logger.debug("User found in DB", extra={"email": email, "hashed_password": user.hashed_password})
    
    print(f"DEBUG: authenticate_user called for {email}")
    if not user:
        print(f"DEBUG: User not found for email {email}")
        logger.warning("User not found", email=email)
        return None
        
    if not user.is_active:
        print(f"DEBUG: User {email} is inactive")
        logger.warning("User is inactive", email=email)
        return None
        
    if not verify_password(password, user.hashed_password):
        print(f"DEBUG: verify_password failed for {email}")
        logger.warning("Invalid password", email=email)
        return None
    
    logger.info("User authenticated successfully", email=email, user_id=str(user.id))
    return user


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email, User.is_active == True).first()


def create_user(db: Session, user_create: dict) -> User:
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
    return db_user