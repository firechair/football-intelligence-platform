"""
Pydantic models for password recovery functionality.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class PasswordResetRequest(BaseModel):
    """Request model for initiating password reset."""
    email: EmailStr = Field(..., description="User's email address")

class PasswordResetConfirm(BaseModel):
    """Request model for confirming password reset."""
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")

class PasswordResetResponse(BaseModel):
    """Response model for password reset operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")

class TokenValidationResponse(BaseModel):
    """Response model for token validation."""
    valid: bool = Field(..., description="Whether the token is valid")
    message: str = Field(..., description="Validation message")
    user_email: Optional[str] = Field(None, description="User email if token is valid")
