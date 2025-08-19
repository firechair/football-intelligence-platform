"""
Password Recovery Service for handling password reset functionality.
"""
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import User
from app.services.auth import get_password_hash
from app.services.email_service import email_service
from app.services.security import security_service

logger = logging.getLogger(__name__)

class PasswordRecoveryService:
    """Service for handling password recovery operations."""
    
    def __init__(self):
        # Token expires in 1 hour
        self.token_expiry_hours = 1
    
    def generate_reset_token(self) -> str:
        """Generate a secure password reset token."""
        return secrets.token_urlsafe(32)
    
    def initiate_password_reset(self, db: Session, email: str) -> Tuple[bool, str]:
        """
        Initiate password reset process.
        
        Args:
            db: Database session
            email: User email address
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check rate limiting for password reset requests
            client_id = f"password_reset_{email}"
            if security_service.is_rate_limited(client_id, max_requests=3, window_minutes=15):
                return False, "Too many password reset requests. Please try again in 15 minutes."
            
            # Find user by email
            user = db.query(User).filter(User.email == email).first()
            
            # Always record the attempt for rate limiting
            security_service.record_attempt(client_id)
            
            # Don't reveal if email exists or not for security reasons
            if not user:
                logger.warning(f"Password reset requested for non-existent email: {email}")
                # Still return success to prevent email enumeration
                return True, "If your email address is in our system, you will receive a password reset link shortly."
            
            # Generate reset token and set expiry
            reset_token = self.generate_reset_token()
            expires_at = datetime.utcnow() + timedelta(hours=self.token_expiry_hours)
            
            # Update user with reset token
            user.password_reset_token = reset_token
            user.password_reset_expires = expires_at
            db.commit()
            
            # Send password reset email
            email_sent = email_service.send_password_reset_email(
                to_email=user.email,
                username=user.username,
                reset_token=reset_token
            )
            
            if email_sent:
                logger.info(f"Password reset email sent to {user.email}")
                return True, "If your email address is in our system, you will receive a password reset link shortly."
            else:
                logger.error(f"Failed to send password reset email to {user.email}")
                # Clear the token if email failed
                user.password_reset_token = None
                user.password_reset_expires = None
                db.commit()
                return False, "Failed to send password reset email. Please try again later."
                
        except Exception as e:
            logger.error(f"Error initiating password reset for {email}: {str(e)}")
            db.rollback()
            return False, "An error occurred. Please try again later."
    
    def verify_reset_token(self, db: Session, token: str) -> Optional[User]:
        """
        Verify password reset token and return user if valid.
        
        Args:
            db: Database session
            token: Reset token to verify
            
        Returns:
            User if token is valid, None otherwise
        """
        try:
            user = db.query(User).filter(
                and_(
                    User.password_reset_token == token,
                    User.password_reset_expires > datetime.utcnow()
                )
            ).first()
            
            return user
            
        except Exception as e:
            logger.error(f"Error verifying reset token: {str(e)}")
            return None
    
    def reset_password(self, db: Session, token: str, new_password: str) -> Tuple[bool, str]:
        """
        Reset user password with provided token.
        
        Args:
            db: Database session
            token: Reset token
            new_password: New password
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate password strength
            password_valid, password_error = security_service.validate_password_strength(new_password)
            if not password_valid:
                return False, password_error
            
            # Verify token
            user = self.verify_reset_token(db, token)
            if not user:
                return False, "Invalid or expired reset token."
            
            # Check rate limiting for password reset attempts
            client_id = f"password_reset_attempt_{user.id}"
            if security_service.is_rate_limited(client_id, max_requests=5, window_minutes=15):
                return False, "Too many password reset attempts. Please try again in 15 minutes."
            
            security_service.record_attempt(client_id)
            
            # Hash new password
            hashed_password = get_password_hash(new_password)
            
            # Update user password and clear reset token
            user.hashed_password = hashed_password
            user.password_reset_token = None
            user.password_reset_expires = None
            
            # If user had 2FA enabled, disable it for security (they can re-enable it)
            if user.two_factor_enabled:
                user.two_factor_enabled = False
                user.two_factor_secret = None
                user.backup_codes = None
                logger.info(f"2FA disabled for user {user.id} after password reset")
            
            db.commit()
            
            logger.info(f"Password reset successful for user {user.id}")
            return True, "Password reset successfully. You can now log in with your new password."
            
        except Exception as e:
            logger.error(f"Error resetting password with token {token}: {str(e)}")
            db.rollback()
            return False, "An error occurred while resetting your password. Please try again."
    
    def cleanup_expired_tokens(self, db: Session) -> int:
        """
        Clean up expired password reset tokens.
        
        Args:
            db: Database session
            
        Returns:
            Number of tokens cleaned up
        """
        try:
            expired_users = db.query(User).filter(
                and_(
                    User.password_reset_token.isnot(None),
                    User.password_reset_expires < datetime.utcnow()
                )
            ).all()
            
            count = 0
            for user in expired_users:
                user.password_reset_token = None
                user.password_reset_expires = None
                count += 1
            
            if count > 0:
                db.commit()
                logger.info(f"Cleaned up {count} expired password reset tokens")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired reset tokens: {str(e)}")
            db.rollback()
            return 0

# Create global instance
password_recovery_service = PasswordRecoveryService()
