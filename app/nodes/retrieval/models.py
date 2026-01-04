from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.storage.models import SearchResult

class RetrievalInput(BaseModel):
    question: str
    
class RetrievalOutput(BaseModel):
    docs: List[str]
    scores: List[float]
    confidence: float
    best_doc_metadata: Dict[str, Any]
    vector_results: Optional[List[SearchResult]] = None
