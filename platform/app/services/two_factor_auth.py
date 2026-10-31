import pyotp
import qrcode
import secrets
import io
import base64
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from app.db.models import User
from app.services.security import security_service

logger = logging.getLogger(__name__)

class TwoFactorAuthService:
    """Service for Two-Factor Authentication using TOTP"""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_qr_code(user_email: str, secret: str, issuer_name: str = "FIP") -> str:
        """Generate QR code for TOTP setup"""
        try:
            # Create TOTP URL
            totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user_email,
                issuer_name=issuer_name
            )
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(totp_uri)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64 string
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate QR code"
            )
    
    @staticmethod
    def verify_totp(secret: str, token: str, window: int = 1) -> bool:
        """Verify TOTP token"""
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, window=window)
        except Exception as e:
            logger.error(f"Error verifying TOTP: {e}")
            return False
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate backup codes for 2FA"""
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(code)
        return codes
    
    @staticmethod
    def verify_backup_code(user: User, code: str) -> bool:
        """Verify and consume a backup code"""
        if not user.backup_codes:
            return False
        
        try:
            backup_codes = user.backup_codes if isinstance(user.backup_codes, list) else json.loads(user.backup_codes)
            
            # Find and remove the used code
            code_upper = code.upper().strip()
            if code_upper in backup_codes:
                backup_codes.remove(code_upper)
                user.backup_codes = backup_codes
                logger.info(f"Backup code used for user {user.id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying backup code: {e}")
            return False
    
    @staticmethod
    def setup_2fa(user: User, secret: str, backup_codes: List[str]) -> bool:
        """Complete 2FA setup for user"""
        try:
            user.two_factor_secret = secret
            user.backup_codes = backup_codes
            user.two_factor_enabled = True
            
            logger.info(f"2FA setup completed for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up 2FA: {e}")
            return False
    
    @staticmethod
    def disable_2fa(user: User) -> bool:
        """Disable 2FA for user"""
        try:
            user.two_factor_enabled = False
            user.two_factor_secret = None
            user.backup_codes = None
            
            logger.info(f"2FA disabled for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling 2FA: {e}")
            return False
    
    @staticmethod
    def regenerate_backup_codes(user: User) -> List[str]:
        """Regenerate backup codes for user"""
        try:
            new_codes = TwoFactorAuthService.generate_backup_codes()
            user.backup_codes = new_codes
            
            logger.info(f"Backup codes regenerated for user {user.id}")
            return new_codes
            
        except Exception as e:
            logger.error(f"Error regenerating backup codes: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to regenerate backup codes"
            )
    
    @staticmethod
    def create_temp_token(user_id: int, expires_minutes: int = 5) -> str:
        """Create temporary token for 2FA verification"""
        from app.services.auth import SECRET_KEY, ALGORITHM
        from jose import jwt
        
        expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "temp_2fa"
        }
        
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_temp_token(token: str) -> Dict[str, Any]:
        """Verify temporary 2FA token"""
        from app.services.auth import SECRET_KEY, ALGORITHM
        from jose import JWTError, jwt
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            if payload.get("type") != "temp_2fa":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            return payload
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired temporary token"
            )

# Singleton instance
two_factor_service = TwoFactorAuthService()
