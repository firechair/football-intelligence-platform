from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"

class SessionCreate(BaseModel):
    user_id: int
    user_agent: str
    ip_address: str
    refresh_token_jti: str
    device_info: Optional[Dict[str, Any]] = None

class SessionUpdate(BaseModel):
    last_activity: Optional[datetime] = None
    is_active: Optional[bool] = None
    termination_reason: Optional[str] = None

class SessionOut(BaseModel):
    session_id: str
    user_id: int
    device_info: Dict[str, Any]
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool
    termination_reason: Optional[str] = None
    is_current: bool = False  # Indica se è la sessione corrente

    class Config:
        from_attributes = True

class SessionTerminate(BaseModel):
    session_id: str
    reason: Optional[str] = "user_logout"
