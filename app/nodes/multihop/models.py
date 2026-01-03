from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

class ComplexityOutput(BaseModel):
    complexity_level: Literal["simple", "medium", "complex"]
    complexity_score: float  # Итоговый балл
    language: Literal["ru", "en"]
    detected_markers: List[str]  # Найденные слова-маркеры
    num_hops: int  # Рекомендуемое количество хопов (1, 2 или 3)
    confidence: float # Уверенность в детекции

class HopDetail(BaseModel):
    hop_index: int
    query: str
    doc_ids: List[str]
    retrieved_at: float # timestamp or duration

class HopResolverOutput(BaseModel):
    primary_doc: Optional[str] = None # топ-1 документ (ID)
    related_docs: List[str] = Field(default_factory=list) # документы из хопов (IDs)
    hop_chain: List[Dict[str, Any]] = Field(default_factory=list) # детали каждого хопа
    merged_context: str = "" # объединенный контекст
    total_hops_performed: int = 0
    retrieval_time: float = 0.0
    confidence: float = 0.0 # средняя релевантность

class MergedContextSource(BaseModel):
    question: str
    hop_level: int
    score: float
    category: str

class MergedContext(BaseModel):
    combined_text: str
    qa_sources: List[MergedContextSource]
    total_tokens: int
    truncated: bool
