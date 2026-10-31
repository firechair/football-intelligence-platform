from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Dict, Any

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class UserCreate(UserBase):
    password: str
    model_config = ConfigDict(json_schema_extra={"example": {"username": "user1", "email": "user1@email.com", "password": "strongpassword", "full_name": "User One", "preferences": {"favorite_team": "AC Milan"}}})

class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True) 