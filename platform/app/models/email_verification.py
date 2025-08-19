"""
Pydantic models for email verification functionality.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class EmailVerificationRequest(BaseModel):
    """Request model for requesting email verification."""
    email: EmailStr = Field(..., description="User's email address")

class EmailVerificationConfirm(BaseModel):
    """Request model for confirming email verification."""
    token: str = Field(..., min_length=1, description="Email verification token")

class EmailVerificationResponse(BaseModel):
    """Response model for email verification operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")

class EmailVerificationStatus(BaseModel):
    """Response model for email verification status."""
    email_verified: bool = Field(..., description="Whether the email is verified")
    email: Optional[str] = Field(None, description="User's email address")
    verification_pending: bool = Field(..., description="Whether verification is pending")
