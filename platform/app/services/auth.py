from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db import session as db_session, models
from app.services.security import security_service
from app.services.session_manager import session_manager
import os
import json
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", "refreshsecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Ridotto per sicurezza
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    # Ensure 'sub' is a string for JWT compatibility
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Crea refresh token con scadenza più lunga"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": security_service.generate_secure_token(16)  # JWT ID per blacklisting
    })
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_refresh_token(token: str) -> Dict[str, Any]:
    """Verifica e decodifica refresh token"""
    try:
        if security_service.is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked"
            )
        
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

def create_token_pair(user_id: int, request: Request = None, db: Session = None) -> Dict[str, Any]:
    """Crea coppia access + refresh token e sessione"""
    
    # Create refresh token with JTI for session tracking
    jti = security_service.generate_secure_token(16)
    refresh_token_data = {"sub": user_id, "jti": jti}
    refresh_token = create_refresh_token(refresh_token_data)
    
    # Create session info if request provided
    session_info = None
    session_id = None
    if request and db:
        # Extract device/browser info
        user_agent = request.headers.get("User-Agent", "Unknown")
        ip_address = security_service.get_client_identifier(request)
        
        # Create session
        session_info = session_manager.create_session(
            db=db,
            user_id=user_id,
            user_agent=user_agent,
            ip_address=ip_address,
            refresh_token_jti=jti
        )
        
        if session_info:
            session_id = session_info.session_id
    
    # Create access token with session info
    access_token_data = {"sub": user_id}
    if session_id:
        access_token_data["session_id"] = session_id
    
    access_token = create_access_token(data=access_token_data)
    
    result = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
    
    if session_id:
        result["session_id"] = session_id
    
    return result

def get_db():
    db = db_session.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db), request: Request = None):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Check token blacklist
        if security_service.is_token_blacklisted(token):
            logger.warning("Attempt to use blacklisted token")
            raise credentials_exception
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "access":
            raise credentials_exception
        
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
        
        # Get session ID from token if present
        session_id = payload.get("session_id")
        
        # Update session activity if session exists
        if session_id:
            # Check if session is still valid
            session_info = session_manager.get_session_by_id(db, session_id)
            if not session_info or not session_manager.is_session_active(
                db.query(models.Session).filter(models.Session.session_id == session_id).first()
            ):
                logger.warning(f"Access attempt with expired session {session_id}")
                raise credentials_exception
            
            # Update activity
            session_manager.update_activity(db, session_id)
        
        # Cleanup expired sessions periodically (lightweight check)
        if session_id and security_service.generate_secure_token(1) == "1":  # 1/16 chance
            session_manager.cleanup_expired_sessions(db)
        
    except (JWTError, ValueError):
        raise credentials_exception
    
    # Get user using raw SQL to avoid ORM issues
    from sqlalchemy import text
    
    # Try to select with 2FA columns, fall back to basic columns if they don't exist
    try:
        user_data = db.execute(text("""
            SELECT id, username, email, hashed_password, full_name, preferences,
                   created_at, email_verified, two_factor_enabled, two_factor_secret, backup_codes
            FROM users 
            WHERE id = :user_id
            LIMIT 1
        """), {"user_id": user_id}).fetchone()
    except Exception as e:
        if "does not exist" in str(e):
            # Fall back to basic query without 2FA columns
            user_data = db.execute(text("""
                SELECT id, username, email, hashed_password, full_name, preferences, created_at
                FROM users 
                WHERE id = :user_id
                LIMIT 1
            """), {"user_id": user_id}).fetchone()
            
            # Extend user_data with default values for missing fields
            if user_data:
                user_data = type('Row', (), {
                    'id': user_data.id,
                    'username': user_data.username,
                    'email': user_data.email,
                    'hashed_password': user_data.hashed_password,
                    'full_name': user_data.full_name,
                    'preferences': user_data.preferences,
                    'created_at': user_data.created_at,
                    'email_verified': False,
                    'two_factor_enabled': False,
                    'two_factor_secret': None,
                    'backup_codes': None
                })()
        else:
            raise e
    
    if user_data is None:
        raise credentials_exception
    
    # Create user-like object
    class UserResponse:
        def __init__(self, row):
            self.id = row.id
            self.username = row.username  
            self.email = row.email
            self.hashed_password = row.hashed_password
            self.full_name = row.full_name
            self.preferences = json.loads(row.preferences) if row.preferences else {}
            self.created_at = row.created_at
            self.email_verified = row.email_verified or False
            self.two_factor_enabled = row.two_factor_enabled or False
            self.two_factor_secret = row.two_factor_secret
            self.backup_codes = json.loads(row.backup_codes) if row.backup_codes else []
            # Attach session info for convenience
            self._session_id = session_id
    
    return UserResponse(user_data)

def authenticate_user(db: Session, username: str, password: str, request: Request = None) -> Optional[models.User]:
    """Autentica utente con controlli di sicurezza"""
    
    # Rate limiting per username
    if request:
        client_id = security_service.get_client_identifier(request)
        rate_key = f"login:{client_id}:{username}"
        
        if security_service.is_rate_limited(rate_key, max_attempts=5, window_minutes=15):
            logger.warning(f"Rate limit exceeded for login attempt: {username} from {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later."
            )
        
        security_service.record_attempt(rate_key)
    
    # Find user by username or email (using raw SQL to avoid ORM issues)
    from sqlalchemy import text
    
    # Try to select with 2FA columns, fall back to basic columns if they don't exist
    try:
        user_data = db.execute(text("""
            SELECT id, username, email, hashed_password, full_name, preferences,
                   created_at, email_verified, two_factor_enabled, two_factor_secret, backup_codes
            FROM users 
            WHERE username = :username OR email = :username
            LIMIT 1
        """), {"username": username}).fetchone()
    except Exception as e:
        if "does not exist" in str(e):
            # Fall back to basic query without 2FA columns
            logger.info(f"2FA columns missing, using basic query for user: {username}")
            user_data = db.execute(text("""
                SELECT id, username, email, hashed_password, full_name, preferences, created_at
                FROM users 
                WHERE username = :username OR email = :username
                LIMIT 1
            """), {"username": username}).fetchone()
            
            # Extend user_data with default values for missing fields
            if user_data:
                user_data = type('Row', (), {
                    'id': user_data.id,
                    'username': user_data.username,
                    'email': user_data.email,
                    'hashed_password': user_data.hashed_password,
                    'full_name': user_data.full_name,
                    'preferences': user_data.preferences,
                    'created_at': user_data.created_at,
                    'email_verified': False,
                    'two_factor_enabled': False,
                    'two_factor_secret': None,
                    'backup_codes': None
                })()
        else:
            raise e
    
    if not user_data or not verify_password(password, user_data.hashed_password):
        logger.info(f"Failed login attempt for: {username}")
        return None
    
    logger.info(f"Successful login for user: {username}")
    
    # Create a user-like object that mimics models.User
    class UserResponse:
        def __init__(self, row):
            self.id = row.id
            self.username = row.username  
            self.email = row.email
            self.hashed_password = row.hashed_password
            self.full_name = row.full_name
            self.preferences = json.loads(row.preferences) if row.preferences else {}
            self.created_at = row.created_at
            self.email_verified = row.email_verified or False
            self.two_factor_enabled = row.two_factor_enabled or False
            self.two_factor_secret = row.two_factor_secret
            self.backup_codes = json.loads(row.backup_codes) if row.backup_codes else []
    
    return UserResponse(user_data)

def logout_user(token: str, db: Session = None, session_id: str = None, user_id: int = None, logout_all: bool = False):
    """Logout utente aggiungendo token alla blacklist e terminando sessioni"""
    # Blacklist the token
    security_service.blacklist_token(token)
    
    # Terminate sessions if database available
    if db:
        if logout_all and user_id:
            # Logout from all sessions
            terminated = session_manager.terminate_user_sessions(db, user_id, reason="logout_all")
            logger.info(f"User {user_id} logged out from all {terminated} sessions")
        elif session_id:
            # Logout from specific session
            session_manager.terminate_session(db, session_id, reason="logout")
            logger.info(f"User logged out, session {session_id} terminated")
        else:
            logger.info("User logged out, token blacklisted")
    else:
        logger.info("User logged out, token blacklisted")

def validate_password_policy(password: str) -> Dict[str, Any]:
    """Valida password secondo policy di sicurezza"""
    return security_service.validate_password_strength(password) 