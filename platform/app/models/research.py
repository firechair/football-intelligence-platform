from pydantic import BaseModel, ConfigDict
from typing import List

class ResearchQuery(BaseModel):
    query: str
    model_config = ConfigDict(json_schema_extra={"example": {"query": "Latest news on AC Milan"}})

class ResearchResult(BaseModel):
    query: str
    results: List[str]
    model_config = ConfigDict(from_attributes=True) 