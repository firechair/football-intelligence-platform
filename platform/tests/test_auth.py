"""
Tests for authentication services
"""
import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.services import auth
from app.services.security import security_service
from app.db import models


class TestPasswordHashing:
    def test_verify_password(self):
        """Test password verification"""
        password = "testpassword123"
        hashed = auth.get_password_hash(password)
        
        assert auth.verify_password(password, hashed) is True
        assert auth.verify_password("wrongpassword", hashed) is False
    
    def test_get_password_hash(self):
        """Test password hashing"""
        password = "testpassword123"
        hashed = auth.get_password_hash(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 10


class TestTokenCreation:
    def test_create_access_token(self):
        """Test access token creation"""
        user_id = 123
        token = auth.create_access_token(data={"sub": user_id})
        
        assert token is not None
        
        # Decode token to verify contents
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        user_id = 123
        token = auth.create_refresh_token(data={"sub": user_id})
        
        assert token is not None
        
        # Decode token to verify contents
        payload = jwt.decode(token, auth.REFRESH_SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "jti" in payload
        assert "exp" in payload
    
    def test_create_token_pair_without_session(self):
        """Test token pair creation without session info"""
        user_id = 123
        tokens = auth.create_token_pair(user_id)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
    
    def test_create_token_pair_with_session(self, db_session, mock_request):
        """Test token pair creation with session info"""
        user_id = 123
        tokens = auth.create_token_pair(user_id, mock_request, db_session)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "session_id" in tokens
        
        # Verify session was created in database
        session = db_session.query(models.Session).filter(
            models.Session.session_id == tokens["session_id"]
        ).first()
        assert session is not None
        assert session.user_id == user_id


class TestTokenValidation:
    def test_verify_refresh_token_valid(self):
        """Test valid refresh token verification"""
        user_id = 123
        token = auth.create_refresh_token(data={"sub": user_id})
        
        payload = auth.verify_refresh_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
    
    def test_verify_refresh_token_blacklisted(self):
        """Test blacklisted refresh token verification"""
        user_id = 123
        token = auth.create_refresh_token(data={"sub": user_id})
        
        # Blacklist token
        security_service.blacklist_token(token)
        
        with pytest.raises(Exception):
            auth.verify_refresh_token(token)
    
    def test_verify_refresh_token_wrong_type(self):
        """Test access token used as refresh token"""
        user_id = 123
        access_token = auth.create_access_token(data={"sub": user_id})
        
        with pytest.raises(Exception):
            auth.verify_refresh_token(access_token)


class TestTokenBlacklisting:
    def test_logout_user(self):
        """Test user logout with token blacklisting"""
        token = "test_token_12345"
        
        auth.logout_user(token)
        
        assert security_service.is_token_blacklisted(token) is True
    
    def test_logout_user_with_session(self, db_session, test_user, mock_request):
        """Test user logout with session termination"""
        # Create session first
        tokens = auth.create_token_pair(test_user.id, mock_request, db_session)
        session_id = tokens["session_id"]
        
        # Verify session exists
        session = db_session.query(models.Session).filter(
            models.Session.session_id == session_id
        ).first()
        assert session.is_active is True
        
        # Logout
        auth.logout_user(tokens["access_token"], db_session, session_id, test_user.id)
        
        # Verify token is blacklisted
        assert security_service.is_token_blacklisted(tokens["access_token"]) is True
        
        # Verify session is terminated
        db_session.refresh(session)
        assert session.is_active is False
        assert session.termination_reason == "logout"


class TestUserAuthentication:
    def test_authenticate_user_valid(self, db_session, test_user):
        """Test valid user authentication"""
        authenticated_user = auth.authenticate_user(
            db_session, "testuser", "testpassword123"
        )
        
        assert authenticated_user is not None
        assert authenticated_user.username == "testuser"
        assert authenticated_user.email == "test@example.com"
    
    def test_authenticate_user_invalid_password(self, db_session, test_user):
        """Test authentication with invalid password"""
        authenticated_user = auth.authenticate_user(
            db_session, "testuser", "wrongpassword"
        )
        
        assert authenticated_user is None
    
    def test_authenticate_user_invalid_username(self, db_session):
        """Test authentication with invalid username"""
        authenticated_user = auth.authenticate_user(
            db_session, "nonexistentuser", "anypassword"
        )
        
        assert authenticated_user is None
    
    def test_authenticate_user_with_email(self, db_session, test_user):
        """Test authentication using email instead of username"""
        authenticated_user = auth.authenticate_user(
            db_session, "test@example.com", "testpassword123"
        )
        
        assert authenticated_user is not None
        assert authenticated_user.username == "testuser"
    
    def test_authenticate_user_rate_limiting(self, db_session, test_user, mock_request):
        """Test rate limiting during authentication"""
        # Make multiple failed attempts
        for _ in range(6):
            try:
                auth.authenticate_user(
                    db_session, "testuser", "wrongpassword", mock_request
                )
            except Exception:
                pass  # Expected to fail with rate limiting
        
        # Should be rate limited now
        with pytest.raises(Exception) as exc_info:
            auth.authenticate_user(
                db_session, "testuser", "testpassword123", mock_request
            )
        
        assert "Too many login attempts" in str(exc_info.value)


class TestPasswordPolicy:
    def test_validate_password_policy_strong(self):
        """Test password policy validation for strong password"""
        result = auth.validate_password_policy("MyStrongP@ssw0rd123")
        
        assert result["valid"] is True
        assert result["strength"] == "forte"
        assert result["score"] == 6
    
    def test_validate_password_policy_weak(self):
        """Test password policy validation for weak password"""
        result = auth.validate_password_policy("123456")
        
        assert result["valid"] is False
        assert result["strength"] == "debole"
        assert result["score"] < 4
        assert len(result["errors"]) > 0
