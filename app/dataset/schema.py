from typing import Optional, List
from pydantic import BaseModel

class EvalItem(BaseModel):
    question: str
    expected_chunks: List[str]
    expected_answer: Optional[str] = None
    expected_intent: Optional[str] = None
    expected_category: Optional[str] = None
    expected_action: Optional[str] = None
