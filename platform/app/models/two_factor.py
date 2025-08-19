from pydantic import BaseModel, Field
from typing import Optional, List

class TwoFactorSetupRequest(BaseModel):
    password: str = Field(..., min_length=1)

class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]
    setup_complete: bool = False

class TwoFactorVerifyRequest(BaseModel):
    token: str = Field(..., min_length=6, max_length=6)

class TwoFactorDisableRequest(BaseModel):
    password: str = Field(..., min_length=1)
    token: Optional[str] = Field(None, min_length=6, max_length=6)

class BackupCodeRequest(BaseModel):
    backup_code: str = Field(..., min_length=8, max_length=8)

class TempTokenResponse(BaseModel):
    requires_2fa: bool = True
    temp_token: str
    message: str = "Please provide your 2FA code to complete login"

class TwoFactorLoginRequest(BaseModel):
    temp_token: str
    totp_code: Optional[str] = None
    backup_code: Optional[str] = None
