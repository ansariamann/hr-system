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
from ats_backend.core.config import settings
from .models import User, TokenData

logger = structlog.get_logger(__name__)

def get_pwd_context():
    """Get password context based on environment."""
    if os.getenv("TESTING", "false").lower() == "true":
        return CryptContext(schemes=["plaintext"], deprecated="auto")
    else:
        return CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    pwd_context = get_pwd_context()
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password with SHA-256 pre-hashing for long passwords.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    pwd_context = get_pwd_context()
    
    # For testing, just return the password as-is (plaintext scheme)
    if os.getenv("TESTING", "false").lower() == "true":
        return pwd_context.hash(password)
    
    import hashlib
    
    # Pre-hash with SHA-256 if password exceeds bcrypt's 72-byte limit
    if len(password.encode('utf-8')) > 72:
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with JTI for replay protection.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
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
    """Verify and decode a JWT token with replay protection and security logging.
    
    Args:
        token: JWT token to verify
        db: Optional database session for security logging
        
    Returns:
        TokenData if valid, None otherwise
    """
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
            
            # Log security event for expired token
            if db:
                SecurityLogger.log_security_event(
                    db=db,
                    event_type=SecurityEventType.EXPIRED_TOKEN,
                    severity=SecurityEventSeverity.MEDIUM,
                    details={
                        "token_expired_at": datetime.utcfromtimestamp(exp).isoformat(),
                        "attempted_at": datetime.utcnow().isoformat()
                    },
                    user_id=UUID(user_id_str) if user_id_str else None,
                    email=email
                )
            
            return None
        
        # Check for token replay if JTI is present and replay protection is enabled
        if jti:
            try:
                if settings.token_replay_protection:
                    is_valid = await token_replay_protection.validate_token_usage(jti)
                    if not is_valid:
                        logger.warning("Token replay detected", jti=jti, user_id=user_id_str, email=email)
                        
                        # Log security event for token replay
                        if db:
                            SecurityLogger.log_security_event(
                                db=db,
                                event_type=SecurityEventType.TOKEN_REPLAY,
                                severity=SecurityEventSeverity.HIGH,
                                details={
                                    "jti": jti,
                                    "attempted_at": datetime.utcnow().isoformat()
                                },
                                user_id=UUID(user_id_str) if user_id_str else None,
                                email=email
                            )
                        
                        return None
            except Exception as e:
                logger.error("Token replay protection check failed", error=str(e))
                # Continue without replay protection in case of errors
            
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


async def authenticate_user(
    db: Session, 
    email: str, 
    password: str, 
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[User]:
    """Authenticate a user with email and password, including rate limiting and security logging.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        ip_address: Optional client IP address
        user_agent: Optional client user agent
        
    Returns:
        User if authentication successful, None otherwise
    """
    from .security import rate_limiter, SecurityLogger, SecurityEventType, SecurityEventSeverity
    
    # Check if account is locked
    is_locked, unlock_time = await rate_limiter.is_account_locked(email)
    if is_locked:
        logger.warning("Authentication attempt on locked account", email=email, unlock_time=unlock_time)
        
        SecurityLogger.log_security_event(
            db=db,
            event_type=SecurityEventType.ACCOUNT_LOCKED,
            severity=SecurityEventSeverity.HIGH,
            details={
                "unlock_time": unlock_time.isoformat() if unlock_time else None,
                "attempted_at": datetime.utcnow().isoformat()
            },
            email=email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return None
    
    # Check rate limiting
    identifier = ip_address or email
    is_allowed, remaining = await rate_limiter.check_rate_limit(identifier, "login")
    
    if not is_allowed:
        logger.warning("Rate limit exceeded for login", identifier=identifier, email=email)
        
        SecurityLogger.log_security_event(
            db=db,
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SecurityEventSeverity.MEDIUM,
            details={
                "identifier": identifier,
                "limit_type": "login",
                "attempted_at": datetime.utcnow().isoformat()
            },
            email=email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return None
    
    # Record the attempt
    await rate_limiter.record_attempt(identifier, "login")
    
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        logger.warning("User not found", email=email)
        
        SecurityLogger.log_security_event(
            db=db,
            event_type=SecurityEventType.AUTH_FAILURE,
            severity=SecurityEventSeverity.LOW,
            details={
                "reason": "user_not_found",
                "attempted_at": datetime.utcnow().isoformat()
            },
            email=email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return None
        
    if not user.is_active:
        logger.warning("User is inactive", email=email)
        
        SecurityLogger.log_security_event(
            db=db,
            event_type=SecurityEventType.AUTH_FAILURE,
            severity=SecurityEventSeverity.MEDIUM,
            details={
                "reason": "user_inactive",
                "attempted_at": datetime.utcnow().isoformat()
            },
            user_id=user.id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return None
        
    if not verify_password(password, user.hashed_password):
        logger.warning("Invalid password", email=email)
        
        SecurityLogger.log_security_event(
            db=db,
            event_type=SecurityEventType.AUTH_FAILURE,
            severity=SecurityEventSeverity.MEDIUM,
            details={
                "reason": "invalid_password",
                "attempted_at": datetime.utcnow().isoformat()
            },
            user_id=user.id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Check if we should lock the account after too many failures
        failed_key = f"rate_limit:login:{identifier}"
        try:
            from ats_backend.core.redis import get_redis
            redis_client = await get_redis()
            failed_count = await redis_client.get(failed_key)
            
            if failed_count and int(failed_count) >= rate_limiter.login_attempts_limit:
                await rate_limiter.lock_account(email)
                
                SecurityLogger.log_security_event(
                    db=db,
                    event_type=SecurityEventType.ACCOUNT_LOCKED,
                    severity=SecurityEventSeverity.HIGH,
                    details={
                        "reason": "too_many_failed_attempts",
                        "failed_attempts": int(failed_count),
                        "locked_at": datetime.utcnow().isoformat()
                    },
                    user_id=user.id,
                    email=email,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
        except Exception as e:
            logger.error("Failed to check/set account lock", error=str(e))
        
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