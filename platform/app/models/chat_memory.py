from pydantic import BaseModel, ConfigDict
from typing import Optional

class ChatMemoryBase(BaseModel):
    memory_context: str

class ChatMemoryCreate(ChatMemoryBase):
    model_config = ConfigDict(json_schema_extra={"example": {"memory_context": "User: Hi!\nBot: Hello! How can I help you today?"}})

class ChatMemoryOut(ChatMemoryBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True) 