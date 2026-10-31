"""
Tests for user API endpoints
"""
import pytest
from fastapi import status


class TestUserRegistration:
    def test_register_user_success(self, client):
        """Test successful user registration"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongP@ssw0rd123",
            "full_name": "New User"
        }
        
        response = client.post("/api/users/register", json=user_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert "hashed_password" not in data  # Password should not be returned
    
    def test_register_user_duplicate_username(self, client, test_user):
        """Test registration with duplicate username"""
        user_data = {
            "username": "testuser",  # Same as test_user
            "email": "different@example.com",
            "password": "StrongP@ssw0rd123"
        }
        
        response = client.post("/api/users/register", json=user_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_register_user_duplicate_email(self, client, test_user):
        """Test registration with duplicate email"""
        user_data = {
            "username": "differentuser",
            "email": "test@example.com",  # Same as test_user
            "password": "StrongP@ssw0rd123"
        }
        
        response = client.post("/api/users/register", json=user_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_register_user_weak_password(self, client):
        """Test registration with weak password"""
        user_data = {
            "username": "weakpassuser",
            "email": "weak@example.com",
            "password": "123456"  # Weak password
        }
        
        response = client.post("/api/users/register", json=user_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.json()["detail"].lower()
    
    def test_register_user_invalid_username(self, client):
        """Test registration with invalid username format"""
        user_data = {
            "username": "us",  # Too short
            "email": "invalid@example.com",
            "password": "StrongP@ssw0rd123"
        }
        
        response = client.post("/api/users/register", json=user_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_user_invalid_email(self, client):
        """Test registration with invalid email format"""
        user_data = {
            "username": "validuser",
            "email": "not-an-email",
            "password": "StrongP@ssw0rd123"
        }
        
        response = client.post("/api/users/register", json=user_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUserLogin:
    def test_login_success(self, client, test_user):
        """Test successful user login"""
        login_data = {
            "username": "testuser",
            "password": "testpassword123"
        }
        
        response = client.post("/api/users/login", data=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "session_id" in data  # Should include session info
    
    def test_login_with_email(self, client, test_user):
        """Test login using email instead of username"""
        login_data = {
            "username": "test@example.com",
            "password": "testpassword123"
        }
        
        response = client.post("/api/users/login", data=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
    
    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials"""
        login_data = {
            "username": "testuser",
            "password": "wrongpassword"
        }
        
        response = client.post("/api/users/login", data=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user"""
        login_data = {
            "username": "nonexistent",
            "password": "anypassword"
        }
        
        response = client.post("/api/users/login", data=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserProfile:
    def test_get_current_user(self, client, auth_headers):
        """Test getting current user profile"""
        response = client.get("/api/users/me", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
    
    def test_get_current_user_unauthorized(self, client):
        """Test getting current user without authentication"""
        response = client.get("/api/users/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_profile(self, client, auth_headers):
        """Test getting user profile"""
        response = client.get("/api/users/profile", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
    
    def test_update_profile(self, client, auth_headers):
        """Test updating user profile"""
        update_data = {
            "full_name": "Updated Name",
            "preferences": {"theme": "dark"}
        }
        
        response = client.patch("/api/users/profile", json=update_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["preferences"]["theme"] == "dark"


class TestTokenOperations:
    def test_refresh_token(self, client, test_user_tokens):
        """Test token refresh"""
        refresh_data = {
            "refresh_token": test_user_tokens["refresh_token"]
        }
        
        response = client.post("/api/users/refresh", json=refresh_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != test_user_tokens["access_token"]  # Should be new token
    
    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token"""
        refresh_data = {
            "refresh_token": "invalid_token"
        }
        
        response = client.post("/api/users/refresh", json=refresh_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_logout(self, client, auth_headers):
        """Test user logout"""
        response = client.post("/api/users/logout", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "Successfully logged out" in data["message"]
    
    def test_logout_all_sessions(self, client, auth_headers):
        """Test logout from all sessions"""
        logout_data = {"logout_all": True}
        
        response = client.post("/api/users/logout", json=logout_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "all sessions" in data["message"].lower()


class TestPasswordStrengthCheck:
    def test_check_password_strength_strong(self, client):
        """Test password strength check for strong password"""
        password_data = {"password": "VeryStr0ng@Passw0rd!"}
        
        response = client.post("/api/users/check-password-strength", json=password_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["strength"] in ["Strong", "Very Strong"]
        assert data["score"] >= 70
    
    def test_check_password_strength_weak(self, client):
        """Test password strength check for weak password"""
        password_data = {"password": "123456"}
        
        response = client.post("/api/users/check-password-strength", json=password_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert data["strength"] in ["Very Weak", "Weak"]
        assert data["score"] < 50
        assert len(data["errors"]) > 0
