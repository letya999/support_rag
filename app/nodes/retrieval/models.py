from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class RetrievalInput(BaseModel):
    question: str
    
class RetrievalOutput(BaseModel):
    docs: List[str]
    scores: List[float]
    confidence: float
    best_doc_metadata: Dict[str, Any]
