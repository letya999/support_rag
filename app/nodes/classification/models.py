from typing import Optional
from pydantic import BaseModel

class ClassificationOutput(BaseModel):
    intent: str
    intent_confidence: float
    category: str
    category_confidence: float
