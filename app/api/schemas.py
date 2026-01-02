from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class SearchRequest(BaseModel):
    q: str
    top_k: int = 3

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    docs: List[str]
    metadata: Dict[str, Any]
