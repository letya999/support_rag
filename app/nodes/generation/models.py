from typing import List
from pydantic import BaseModel

class GenerationInput(BaseModel):
    question: str
    docs: List[str]

class GenerationOutput(BaseModel):
    answer: str
