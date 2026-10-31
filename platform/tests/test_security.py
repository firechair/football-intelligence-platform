"""
Tests for security services
"""
import pytest
import time
from unittest.mock import Mock

from app.services.security import security_service


class TestPasswordStrengthValidation:
    def test_validate_password_strength_strong(self):
        """Test strong password validation"""
        result = security_service.validate_password_strength("MyStrongP@ssw0rd123")
        
        assert result["valid"] is True
        assert result["strength"] == "forte"
        assert result["score"] == 6
        assert len(result["errors"]) == 0
    
    def test_validate_password_strength_weak(self):
        """Test weak password validation"""
        result = security_service.validate_password_strength("123456")
        
        assert result["valid"] is False
        assert result["strength"] == "debole"
        assert result["score"] < 4
        assert len(result["errors"]) > 0
    
    def test_validate_password_strength_medium(self):
        """Test medium strength password"""
        result = security_service.validate_password_strength("Password123")
        
        assert result["score"] >= 4
        assert result["strength"] in ["media", "forte"]
    
    def test_validate_password_strength_empty(self):
        """Test empty password"""
        result = security_service.validate_password_strength("")
        
        assert result["valid"] is False
        assert "Password deve essere almeno 6 caratteri" in result["errors"]
    
    def test_validate_password_strength_too_short(self):
        """Test password too short"""
        result = security_service.validate_password_strength("Ab1!")
        
        assert result["valid"] is False
        assert "Password deve essere almeno 6 caratteri" in result["errors"]


class TestRateLimiting:
    def test_rate_limiting_under_limit(self):
        """Test rate limiting under the limit"""
        key = "test_key_1"
        
        # Should not be rate limited initially
        assert security_service.is_rate_limited(key, max_attempts=5, window_minutes=1) is False
        
        # Record attempts under the limit
        for _ in range(4):
            security_service.record_attempt(key)
        
        # Should still not be rate limited
        assert security_service.is_rate_limited(key, max_attempts=5, window_minutes=1) is False
    
    def test_rate_limiting_over_limit(self):
        """Test rate limiting over the limit"""
        key = "test_key_2"
        
        # Record attempts over the limit
        for _ in range(6):
            security_service.record_attempt(key)
        
        # Should be rate limited
        assert security_service.is_rate_limited(key, max_attempts=5, window_minutes=1) is True
    
    def test_rate_limiting_window_expiry(self):
        """Test rate limiting window expiry"""
        key = "test_key_3"
        
        # Set a very short window
        window_minutes = 0.01  # ~0.6 seconds
        
        # Exceed the limit
        for _ in range(6):
            security_service.record_attempt(key)
        
        # Should be rate limited
        assert security_service.is_rate_limited(key, max_attempts=5, window_minutes=window_minutes) is True
        
        # Exceeding the limit blocks the key for twice the window
        time.sleep(1.3)
        
        # Should not be rate limited anymore
        assert security_service.is_rate_limited(key, max_attempts=5, window_minutes=window_minutes) is False


class TestInputSanitization:
    def test_sanitize_input_normal(self):
        """Test normal input sanitization"""
        result = security_service.sanitize_input("Hello World", max_length=50)
        assert result == "Hello World"
    
    def test_sanitize_input_with_html(self):
        """Test HTML tag removal"""
        result = security_service.sanitize_input("<script>alert('xss')</script>Hello", max_length=50)
        assert "<script>" not in result
        assert "Hello" in result
    
    def test_sanitize_input_with_sql(self):
        """Test SQL injection pattern removal"""
        result = security_service.sanitize_input("'; DROP TABLE users; --", max_length=50)
        # Queries are parameterized; sanitize_input only strips the characters that break out of a string
        assert "'" not in result
    
    def test_sanitize_input_max_length(self):
        """Test max length enforcement"""
        long_text = "A" * 100
        result = security_service.sanitize_input(long_text, max_length=50)
        assert len(result) <= 50
    
    def test_sanitize_input_empty(self):
        """Test empty input"""
        result = security_service.sanitize_input("", max_length=50)
        assert result == ""
    
    def test_sanitize_input_none(self):
        """Test None input"""
        result = security_service.sanitize_input(None, max_length=50)
        assert result == ""


class TestUsernameValidation:
    def test_validate_username_format_valid(self):
        """Test valid username formats"""
        valid_usernames = ["user123", "test_user", "ValidUser", "abc", "a1b2c3", "user-name", "user.name"]
        
        for username in valid_usernames:
            result = security_service.validate_username_format(username)
            assert result["valid"] is True, f"Username '{username}' should be valid"
            assert len(result["errors"]) == 0
    
    def test_validate_username_format_invalid(self):
        """Test invalid username formats"""
        invalid_usernames = [
            "",  # too short
            "ab",  # too short  
            "a" * 51,  # too long
            "user@name",  # contains @
            "user name",  # contains space
            ".username",  # starts with a dot
            "username.",  # ends with a dot
        ]
        
        for username in invalid_usernames:
            result = security_service.validate_username_format(username)
            assert result["valid"] is False, f"Username '{username}' should be invalid"
            assert len(result["errors"]) > 0


class TestEmailValidation:
    def test_validate_email_format_valid(self):
        """Test valid email formats"""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk", 
            "user+tag@example.org",
            "123@example.com"
        ]
        
        for email in valid_emails:
            assert security_service.validate_email_format(email) is True, f"Email '{email}' should be valid"
    
    def test_validate_email_format_invalid(self):
        """Test invalid email formats"""
        invalid_emails = [
            "",  # empty
            "notanemail",  # no @
            "@example.com",  # no local part
            "user@",  # no domain
            "user@domain",  # no TLD
            "user name@example.com",  # space in local part
            "a" * 100 + "@example.com",  # too long
        ]
        
        for email in invalid_emails:
            assert security_service.validate_email_format(email) is False, f"Email '{email}' should be invalid"


class TestTokenBlacklisting:
    def test_blacklist_token(self):
        """Test token blacklisting"""
        token = "test_token_123"
        
        # Initially not blacklisted
        assert security_service.is_token_blacklisted(token) is False
        
        # Blacklist token
        security_service.blacklist_token(token)
        
        # Should be blacklisted
        assert security_service.is_token_blacklisted(token) is True
    
    def test_blacklist_multiple_tokens(self):
        """Test blacklisting multiple tokens"""
        tokens = ["token_1", "token_2", "token_3"]
        
        # Blacklist all tokens
        for token in tokens:
            security_service.blacklist_token(token)
        
        # All should be blacklisted
        for token in tokens:
            assert security_service.is_token_blacklisted(token) is True
        
        # Non-blacklisted token should not be affected
        assert security_service.is_token_blacklisted("token_4") is False


class TestClientIdentification:
    def test_get_client_identifier_with_forwarded_for(self):
        """Test client identification with X-Forwarded-For header"""
        mock_request = Mock()
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        client_id = security_service.get_client_identifier(mock_request)
        assert client_id == "192.168.1.1"
    
    def test_get_client_identifier_with_real_ip(self):
        """Test client identification with X-Real-IP header"""
        mock_request = Mock()
        mock_request.headers = {"X-Real-IP": "192.168.1.2"}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        client_id = security_service.get_client_identifier(mock_request)
        assert client_id == "192.168.1.2"
    
    def test_get_client_identifier_fallback_to_client_host(self):
        """Test client identification fallback to client.host"""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        client_id = security_service.get_client_identifier(mock_request)
        assert client_id == "127.0.0.1"
    
    def test_get_client_identifier_no_client(self):
        """Test client identification with no client info"""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client = None
        
        client_id = security_service.get_client_identifier(mock_request)
        assert client_id == "unknown"


class TestSecureTokenGeneration:
    def test_generate_secure_token_default_length(self):
        """Test secure token generation with default length"""
        token = security_service.generate_secure_token()
        assert len(token) >= 32  # token_urlsafe: 32 random bytes, longer once encoded
        assert isinstance(token, str)
    
    def test_generate_secure_token_custom_length(self):
        """Test secure token generation with custom length"""
        lengths = [8, 16, 64]
        for length in lengths:
            token = security_service.generate_secure_token(length)
            assert len(token) >= length  # token_urlsafe: base64 grows the random bytes
            assert isinstance(token, str)
    
    def test_generate_secure_token_uniqueness(self):
        """Test that generated tokens are unique"""
        tokens = set()
        for _ in range(100):
            token = security_service.generate_secure_token()
            tokens.add(token)
        
        # Should have 100 unique tokens
        assert len(tokens) == 100
