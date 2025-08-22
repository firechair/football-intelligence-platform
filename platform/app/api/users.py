from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.models.user import UserCreate, UserOut
from app.db import session as db_session, models
from app.services import auth
from app.services import user_service
from app.services.security import security_service
from app.services.session_manager import session_manager
from app.services.two_factor_auth import two_factor_service
from typing import List, Optional
import json
from app.models.token import Token, TokenRefresh, TokenResponse
from app.models.session import SessionOut, SessionTerminate
from app.models.two_factor import (
    TwoFactorSetupRequest, TwoFactorSetupResponse,
    TwoFactorVerifyRequest, TwoFactorDisableRequest,
    TempTokenResponse, TwoFactorLoginRequest
)
from app.models.password_recovery import (
    PasswordResetRequest, PasswordResetConfirm,
    PasswordResetResponse, TokenValidationResponse
)
from app.models.email_verification import (
    EmailVerificationRequest, EmailVerificationConfirm,
    EmailVerificationResponse, EmailVerificationStatus
)
from app.services.password_recovery import password_recovery_service
from app.services.email_verification import email_verification_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

def get_db():
    db = db_session.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=UserOut)
def register_user(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Registra nuovo utente con controlli di sicurezza"""
    
    try:
        logger.info("Registration attempt started")
        
        # Skip rate limiting temporarily to isolate the issue
        # Rate limiting per registrazione
        # client_id = security_service.get_client_identifier(request)
        # rate_key = f"register:{client_id}"
        
        # if security_service.is_rate_limited(rate_key, max_attempts=3, window_minutes=60):
        #     logger.warning(f"Rate limit exceeded for registration from: {client_id}")
        #     raise HTTPException(
        #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        #         detail="Too many registration attempts. Try again later."
        #     )
        
        # security_service.record_attempt(rate_key)
        
        # Sanitize input
        logger.info("Sanitizing input...")
        username = security_service.sanitize_input(user.username, 50)
        email = security_service.sanitize_input(user.email, 100)
        full_name = security_service.sanitize_input(user.full_name or "", 100) if user.full_name else None
        
        # Validate input formats
        logger.info("Validating input formats...")
        username_validation = security_service.validate_username_format(username)
        if not username_validation['valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": username_validation['errors']}
            )
        
        if not security_service.validate_email_format(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password strength
        logger.info("Validating password strength...")
        password_validation = auth.validate_password_policy(user.password)
        if not password_validation['valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"password_errors": password_validation['errors']}
            )
        
        # Check if user already exists (using raw SQL to avoid ORM issues)
        logger.info("Checking if user already exists...")
        from sqlalchemy import text
        
        existing_user = db.execute(text("""
            SELECT username, email FROM users 
            WHERE username = :username OR email = :email 
            LIMIT 1
        """), {"username": username, "email": email}).fetchone()
        
        if existing_user:
            if existing_user.username == username:
                raise HTTPException(status_code=400, detail="Username already registered")
            else:
                raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user (using raw SQL like the working test endpoint)
        logger.info("Creating new user...")
        hashed_password = auth.get_password_hash(user.password)
        
        logger.info("Saving user to database...")
        
        # Insert user using raw SQL 
        result = db.execute(text("""
            INSERT INTO users (username, email, hashed_password, full_name, preferences)
            VALUES (:username, :email, :hashed_password, :full_name, :preferences)
            RETURNING id, username, email, full_name, preferences, created_at, 
                     email_verified, two_factor_enabled
        """), {
            "username": username,
            "email": email, 
            "hashed_password": hashed_password,
            "full_name": full_name,
            "preferences": json.dumps(user.preferences or {})
        })
        
        db.commit()
        
        # Get the created user data
        new_user_data = result.fetchone()
        logger.info(f"User created with ID: {new_user_data.id}")
        
        # Create a user response object manually
        class UserResponse:
            def __init__(self, row):
                self.id = row.id
                self.username = row.username  
                self.email = row.email
                self.full_name = row.full_name
                self.preferences = json.loads(row.preferences) if row.preferences else {}
                self.created_at = row.created_at
                self.email_verified = row.email_verified or False
                self.two_factor_enabled = row.two_factor_enabled or False
        
        new_user = UserResponse(new_user_data)
        
        # Temporarily disable email verification until we fix the service
        logger.info("Email verification temporarily disabled during registration fix")
        # The email verification service expects SQLAlchemy ORM User object
        # but we're now using raw SQL and custom UserResponse object
        # TODO: Fix email verification service to work with raw SQL approach
        
        logger.info(f"New user registered successfully: {username}")
        return new_user
        
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions (validation errors, etc.)
        logger.warning(f"Registration validation error: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Log the actual error that's causing the 500
        logger.error(f"REGISTRATION CRASH: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"REGISTRATION TRACEBACK: {traceback.format_exc()}")
        
        # Return a user-friendly error instead of crashing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Registration failed due to server error: {type(e).__name__}"
    )

@router.post("/test-register")
def test_register_minimal(username: str = Body(...), email: str = Body(...), password: str = Body(...)):
    """Minimal registration test to isolate the issue"""
    try:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        logger.info(f"TEST REGISTRATION: Starting with {username}, {email}")
        
        # Test 1: Basic database connection
        from app.db.session import SessionLocal
        db = SessionLocal()
        
        logger.info("TEST REGISTRATION: Database connection successful")
        
        # Test 2: Simple query
        from sqlalchemy import text
        result = db.execute(text("SELECT 1"))
        test_result = result.scalar()
        
        logger.info(f"TEST REGISTRATION: Simple query result: {test_result}")
        
        # Test 3: Check if users table exists
        try:
            count_result = db.execute(text("SELECT COUNT(*) FROM users"))
            user_count = count_result.scalar()
            logger.info(f"TEST REGISTRATION: Users table has {user_count} records")
        except Exception as table_error:
            logger.error(f"TEST REGISTRATION: Users table error: {table_error}")
            # Try to create the table
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    hashed_password VARCHAR(128) NOT NULL,
                    full_name VARCHAR(120),
                    preferences JSON DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    two_factor_enabled BOOLEAN DEFAULT FALSE,
                    two_factor_secret VARCHAR(255),
                    backup_codes JSON,
                    email_verified BOOLEAN DEFAULT FALSE,
                    email_verification_token VARCHAR(255),
                    email_verification_expires TIMESTAMP,
                    password_reset_token VARCHAR(255),
                    password_reset_expires TIMESTAMP
                )
            """))
            db.commit()
            logger.info("TEST REGISTRATION: Users table created")
        
        # Test 4: Simple password hashing
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(password)
        
        logger.info("TEST REGISTRATION: Password hashed successfully")
        
        # Test 5: Create user record
        db.execute(text("""
            INSERT INTO users (username, email, hashed_password, full_name, preferences)
            VALUES (:username, :email, :hashed_password, 'Test User', '{}')
        """), {"username": username, "email": email, "hashed_password": hashed_password})
        
        db.commit()
        db.close()
        
        logger.info("TEST REGISTRATION: User created successfully")
        
        return {"status": "success", "message": f"Test user {username} created successfully"}
        
    except Exception as e:
        import traceback
        logger.error(f"TEST REGISTRATION ERROR: {type(e).__name__}: {str(e)}")
        logger.error(f"TEST REGISTRATION TRACEBACK: {traceback.format_exc()}")
        return {"status": "error", "error": str(e), "type": type(e).__name__}

@router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)):
    """Login utente con controlli di sicurezza e supporto 2FA"""
    
    # Sanitize input
    username = security_service.sanitize_input(form_data.username, 100)
    
    # Authenticate with security checks
    user = auth.authenticate_user(db, username, form_data.password, request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if 2FA is enabled for this user
    if user.two_factor_enabled:
        # Generate temporary token for 2FA verification
        temp_token = two_factor_service.create_temp_token(user.id)
        logger.info(f"2FA required for user: {user.username}")
        
        return TempTokenResponse(
            temp_token=temp_token,
            message="Please provide your 2FA code to complete login"
        )
    
    # Normal login flow (no 2FA)
    token_data = auth.create_token_pair(user.id, request, db)
    logger.info(f"User logged in: {user.username} (session: {token_data.get('session_id', 'N/A')})")
    
    return token_data

@router.get("/me", response_model=UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/profile", response_model=UserOut)
def get_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.patch("/profile", response_model=UserOut)
def update_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
    full_name: Optional[str] = Body(None),
    preferences: Optional[dict] = Body(None),
):
    # Sanitize input
    if full_name:
        full_name = security_service.sanitize_input(full_name, 100)
    
    return user_service.update_user_profile(
        db=db, user=current_user, full_name=full_name, preferences=preferences
    )

@router.post("/refresh", response_model=Token)
def refresh_token(token_data: TokenRefresh, request: Request = None, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    
    # Verify refresh token
    payload = auth.verify_refresh_token(token_data.refresh_token)
    user_id = int(payload.get("sub"))
    jti = payload.get("jti")
    
    # Verify user still exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Find session by JTI and verify it's still active
    current_session = session_manager.get_session_by_jti(db, jti) if jti else None
    if jti and not current_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )
    
    # Blacklist old refresh token
    auth.logout_user(token_data.refresh_token, db, current_session.session_id if current_session else None)
    
    # Create new token pair
    new_tokens = auth.create_token_pair(user.id, request, db)
    logger.info(f"Tokens refreshed for user: {user.username}")
    
    return new_tokens

@router.post("/logout")
def logout_user_endpoint(
    token: str = Depends(auth.oauth2_scheme),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    logout_all: bool = Body(False, embed=True)
):
    """Logout utente e blacklist del token"""
    session_id = getattr(current_user, '_session_id', None)
    
    auth.logout_user(
        token=token, 
        db=db,
        session_id=session_id, 
        user_id=current_user.id,
        logout_all=logout_all
    )
    
    message = "Successfully logged out from all sessions" if logout_all else "Successfully logged out"
    logger.info(f"User logged out: {current_user.username} (logout_all: {logout_all})")
    return {"message": message}

@router.post("/check-password-strength")
def check_password_strength(password: str = Body(..., embed=True)):
    """Controlla la forza di una password"""
    validation = auth.validate_password_policy(password)
    return {
        "valid": validation['valid'],
        "strength": validation['strength'],
        "score": validation['score'],
        "errors": validation.get('errors', [])
    }

# === SESSION MANAGEMENT ENDPOINTS ===

@router.get("/sessions", response_model=List[SessionOut])
def get_user_sessions(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    include_inactive: bool = False
):
    """Ottieni tutte le sessioni attive dell'utente"""
    sessions = session_manager.get_user_sessions(db, current_user.id, include_inactive)
    
    # Mark current session if available
    current_session_id = getattr(current_user, '_session_id', None)
    if current_session_id:
        for session in sessions:
            session.is_current = (session.session_id == current_session_id)
    
    return sessions

@router.delete("/sessions/{session_id}")
def terminate_session(
    session_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Termina sessione specifica"""
    
    # Verify the session belongs to the current user
    user_sessions = session_manager.get_user_sessions(db, current_user.id, include_inactive=True)
    session_found = any(session.session_id == session_id for session in user_sessions)
    
    if not session_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or doesn't belong to current user"
        )
    
    success = session_manager.terminate_session(db, session_id, reason="user_terminated")
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to terminate session"
        )
    
    logger.info(f"User {current_user.username} terminated session {session_id}")
    return {"message": "Session terminated successfully"}

@router.delete("/sessions")
def terminate_all_sessions(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Termina tutte le sessioni utente eccetto quella corrente"""
    
    current_session_id = getattr(current_user, '_session_id', None)
    terminated_count = session_manager.terminate_user_sessions(
        db, 
        current_user.id, 
        reason="terminate_all",
        exclude_session_id=current_session_id
    )
    
    logger.info(f"User {current_user.username} terminated {terminated_count} sessions")
    return {
        "message": f"Successfully terminated {terminated_count} sessions",
        "terminated_count": terminated_count
    }

# === TWO-FACTOR AUTHENTICATION ENDPOINTS ===

@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_2fa(
    request_data: TwoFactorSetupRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Inizia setup 2FA per l'utente"""
    
    # Verify current password
    if not auth.verify_password(request_data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Check if 2FA is already enabled
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled. Disable it first to reconfigure."
        )
    
    # Generate secret and QR code
    secret = two_factor_service.generate_secret()
    qr_code = two_factor_service.generate_qr_code(current_user.email, secret)
    backup_codes = two_factor_service.generate_backup_codes()
    
    # Store secret temporarily (will be confirmed on verification)
    current_user.two_factor_secret = secret
    current_user.backup_codes = backup_codes
    db.commit()
    
    logger.info(f"2FA setup initiated for user: {current_user.username}")
    
    return TwoFactorSetupResponse(
        secret=secret,
        qr_code=qr_code,
        backup_codes=backup_codes
    )

@router.post("/2fa/verify")
def verify_2fa(
    request_data: TwoFactorVerifyRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Verifica e completa il setup 2FA"""
    
    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No 2FA setup in progress"
        )
    
    # Verify TOTP token
    if not two_factor_service.verify_totp(current_user.two_factor_secret, request_data.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA token"
        )
    
    # Complete setup
    current_user.two_factor_enabled = True
    db.commit()
    
    logger.info(f"2FA setup completed for user: {current_user.username}")
    
    return {"message": "2FA has been successfully enabled", "enabled": True}

@router.post("/2fa/disable")
def disable_2fa(
    request_data: TwoFactorDisableRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Disabilita 2FA per l'utente"""
    
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled"
        )
    
    # Verify current password
    if not auth.verify_password(request_data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # If 2FA token provided, verify it too
    if request_data.token:
        if not two_factor_service.verify_totp(current_user.two_factor_secret, request_data.token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 2FA token"
            )
    
    # Disable 2FA
    two_factor_service.disable_2fa(current_user)
    db.commit()
    
    logger.info(f"2FA disabled for user: {current_user.username}")
    
    return {"message": "2FA has been successfully disabled", "enabled": False}

@router.get("/2fa/backup-codes")
def get_backup_codes(
    current_user: models.User = Depends(auth.get_current_user)
):
    """Ottieni i backup codes dell'utente"""
    
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled"
        )
    
    return {
        "backup_codes": current_user.backup_codes or [],
        "remaining": len(current_user.backup_codes or [])
    }

@router.post("/2fa/backup-codes/regenerate")
def regenerate_backup_codes(
    password: str = Body(..., embed=True),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Rigenera i backup codes"""
    
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled"
        )
    
    # Verify password
    if not auth.verify_password(password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Regenerate codes
    new_codes = two_factor_service.regenerate_backup_codes(current_user)
    db.commit()
    
    logger.info(f"Backup codes regenerated for user: {current_user.username}")
    
    return {
        "message": "Backup codes regenerated successfully",
        "backup_codes": new_codes
    }

@router.post("/2fa/verify-login", response_model=Token)
def verify_2fa_login(
    request_data: TwoFactorLoginRequest,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Verifica 2FA e completa il login"""
    
    # Verify temporary token
    try:
        payload = two_factor_service.verify_temp_token(request_data.temp_token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired temporary token"
        )
    
    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Check if 2FA is enabled
    if not user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this user"
        )
    
    verified = False
    
    # Try TOTP code first
    if request_data.totp_code:
        verified = two_factor_service.verify_totp(user.two_factor_secret, request_data.totp_code)
        
    # Try backup code if TOTP failed
    if not verified and request_data.backup_code:
        verified = two_factor_service.verify_backup_code(user, request_data.backup_code)
        if verified:
            db.commit()  # Save the consumed backup code
    
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code"
        )
    
    # Create token pair and complete login
    token_data = auth.create_token_pair(user.id, request, db)
    logger.info(f"2FA login completed for user: {user.username}")
    
    return token_data

@router.get("/2fa/status")
def get_2fa_status(current_user: models.User = Depends(auth.get_current_user)):
    """Ottieni stato 2FA dell'utente"""
    return {
        "enabled": current_user.two_factor_enabled,
        "backup_codes_remaining": len(current_user.backup_codes or []) if current_user.backup_codes else 0
    }

# Password Recovery Endpoints

@router.post("/password-reset/request", response_model=PasswordResetResponse)
def request_password_reset(
    request_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Richiedi reset password via email"""
    
    client_id = security_service.get_client_identifier(request)
    logger.info(f"Password reset requested for email: {request_data.email} from {client_id}")
    
    success, message = password_recovery_service.initiate_password_reset(db, request_data.email)
    
    if not success:
        logger.warning(f"Password reset failed for {request_data.email}: {message}")
    
    return PasswordResetResponse(success=success, message=message)

@router.post("/password-reset/verify-token", response_model=TokenValidationResponse)  
def verify_reset_token(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """Verifica validità token reset password"""
    
    user = password_recovery_service.verify_reset_token(db, token)
    
    if user:
        return TokenValidationResponse(
            valid=True,
            message="Token is valid",
            user_email=user.email
        )
    else:
        return TokenValidationResponse(
            valid=False,
            message="Invalid or expired token"
        )

@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
def confirm_password_reset(
    request_data: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db)
):
    """Conferma reset password con nuovo password"""
    
    client_id = security_service.get_client_identifier(request)
    logger.info(f"Password reset confirmation attempted from {client_id}")
    
    success, message = password_recovery_service.reset_password(
        db, request_data.token, request_data.new_password
    )
    
    if success:
        logger.info("Password reset completed successfully")
    else:
        logger.warning(f"Password reset confirmation failed: {message}")
    
    return PasswordResetResponse(success=success, message=message)

# Email Verification Endpoints

@router.post("/email-verification/resend", response_model=EmailVerificationResponse)
def resend_verification_email(
    request_data: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reinvia email di verifica"""
    
    client_id = security_service.get_client_identifier(request)
    logger.info(f"Email verification resend requested for: {request_data.email} from {client_id}")
    
    success, message = email_verification_service.resend_verification_email(db, request_data.email)
    
    return EmailVerificationResponse(success=success, message=message)

@router.post("/email-verification/verify", response_model=EmailVerificationResponse)
def verify_email(
    request_data: EmailVerificationConfirm,
    request: Request,
    db: Session = Depends(get_db)
):
    """Verifica email con token"""
    
    client_id = security_service.get_client_identifier(request)
    logger.info(f"Email verification attempted from {client_id}")
    
    success, message = email_verification_service.verify_email_token(db, request_data.token)
    
    if success:
        logger.info("Email verification completed successfully")
    else:
        logger.warning(f"Email verification failed: {message}")
    
    return EmailVerificationResponse(success=success, message=message)

@router.get("/email-verification/status", response_model=EmailVerificationStatus)
def get_email_verification_status(current_user: models.User = Depends(auth.get_current_user)):
    """Ottieni stato verifica email dell'utente"""
    return EmailVerificationStatus(
        email_verified=current_user.email_verified,
        email=current_user.email,
        verification_pending=not current_user.email_verified and current_user.email_verification_token is not None
    ) 