"""
Email Verification Service for handling email verification functionality.
"""
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import User
from app.services.email_service import email_service
from app.services.security import security_service

logger = logging.getLogger(__name__)

class EmailVerificationService:
    """Service for handling email verification operations."""
    
    def __init__(self):
        # Token expires in 24 hours
        self.token_expiry_hours = 24
    
    def generate_verification_token(self) -> str:
        """Generate a secure email verification token."""
        return secrets.token_urlsafe(32)
    
    def send_verification_email(self, db: Session, user: User) -> Tuple[bool, str]:
        """
        Send email verification email to user.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Generate verification token and set expiry
            verification_token = self.generate_verification_token()
            expires_at = datetime.utcnow() + timedelta(hours=self.token_expiry_hours)
            
            # Update user with verification token
            user.email_verification_token = verification_token
            user.email_verification_expires = expires_at
            db.commit()
            
            # Send verification email
            email_sent = email_service.send_email_verification_email(
                to_email=user.email,
                username=user.username,
                verification_token=verification_token
            )
            
            if email_sent:
                logger.info(f"Email verification sent to {user.email}")
                return True, "Verification email sent successfully."
            else:
                logger.error(f"Failed to send verification email to {user.email}")
                # Clear the token if email failed
                user.email_verification_token = None
                user.email_verification_expires = None
                db.commit()
                return False, "Failed to send verification email. Please try again later."
                
        except Exception as e:
            logger.error(f"Error sending verification email for user {user.id}: {str(e)}")
            db.rollback()
            return False, "An error occurred. Please try again later."
    
    def resend_verification_email(self, db: Session, email: str) -> Tuple[bool, str]:
        """
        Resend verification email to user.
        
        Args:
            db: Database session
            email: User email address
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check rate limiting for verification email requests
            client_id = f"email_verification_{email}"
            if security_service.is_rate_limited(client_id, max_requests=3, window_minutes=10):
                return False, "Too many verification email requests. Please try again in 10 minutes."
            
            # Find user by email
            user = db.query(User).filter(User.email == email).first()
            
            # Always record the attempt for rate limiting
            security_service.record_attempt(client_id)
            
            if not user:
                # Don't reveal if email exists or not
                return True, "If your email address is in our system, you will receive a verification email shortly."
            
            if user.email_verified:
                return False, "Email address is already verified."
            
            # Send verification email
            return self.send_verification_email(db, user)
                
        except Exception as e:
            logger.error(f"Error resending verification email for {email}: {str(e)}")
            return False, "An error occurred. Please try again later."
    
    def verify_email_token(self, db: Session, token: str) -> Tuple[bool, str]:
        """
        Verify email verification token.
        
        Args:
            db: Database session
            token: Verification token
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Find user with valid token
            user = db.query(User).filter(
                and_(
                    User.email_verification_token == token,
                    User.email_verification_expires > datetime.utcnow(),
                    User.email_verified == False
                )
            ).first()
            
            if not user:
                return False, "Invalid or expired verification token."
            
            # Mark email as verified and clear token
            user.email_verified = True
            user.email_verification_token = None
            user.email_verification_expires = None
            db.commit()
            
            # Send welcome email
            try:
                email_service.send_welcome_email(user.email, user.username)
            except Exception as e:
                logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
                # Don't fail verification if welcome email fails
            
            logger.info(f"Email verification successful for user {user.id}")
            return True, "Email verified successfully. Welcome to FIP!"
            
        except Exception as e:
            logger.error(f"Error verifying email token {token}: {str(e)}")
            db.rollback()
            return False, "An error occurred while verifying your email. Please try again."
    
    def get_verification_token(self, db: Session, token: str) -> Optional[User]:
        """
        Get user by verification token if valid.
        
        Args:
            db: Database session
            token: Verification token
            
        Returns:
            User if token is valid, None otherwise
        """
        try:
            user = db.query(User).filter(
                and_(
                    User.email_verification_token == token,
                    User.email_verification_expires > datetime.utcnow(),
                    User.email_verified == False
                )
            ).first()
            
            return user
            
        except Exception as e:
            logger.error(f"Error getting verification token: {str(e)}")
            return None
    
    def cleanup_expired_tokens(self, db: Session) -> int:
        """
        Clean up expired email verification tokens.
        
        Args:
            db: Database session
            
        Returns:
            Number of tokens cleaned up
        """
        try:
            expired_users = db.query(User).filter(
                and_(
                    User.email_verification_token.isnot(None),
                    User.email_verification_expires < datetime.utcnow()
                )
            ).all()
            
            count = 0
            for user in expired_users:
                user.email_verification_token = None
                user.email_verification_expires = None
                count += 1
            
            if count > 0:
                db.commit()
                logger.info(f"Cleaned up {count} expired email verification tokens")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired verification tokens: {str(e)}")
            db.rollback()
            return 0
    
    def require_verification_for_sensitive_operations(self, user: User) -> bool:
        """
        Check if user needs email verification for sensitive operations.
        
        Args:
            user: User object
            
        Returns:
            True if verification is required, False otherwise
        """
        return not user.email_verified

# Create global instance
email_verification_service = EmailVerificationService()
