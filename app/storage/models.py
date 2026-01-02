from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class Document(BaseModel):
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
class SearchResult(Document):
    score: float
