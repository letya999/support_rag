from typing import TypedDict, List, Optional, Literal, Dict, Any

class State(TypedDict):
    question: str
    queries: Optional[List[str]]
    docs: List[str]
    rerank_scores: Optional[List[float]]
    answer: Optional[str]
    action: Optional[Literal["auto_reply", "handoff"]]
    confidence: Optional[float]
    matched_intent: Optional[str]
    matched_category: Optional[str]
    best_doc_metadata: Optional[Dict[str, Any]]
    hybrid_used: Optional[bool]
    hybrid_used: Optional[bool]
    confidence_threshold: Optional[float]
    
    # Classification
    intent: Optional[str]
    intent_confidence: Optional[float]
    category: Optional[str]
    category_confidence: Optional[float]
    
    # Filtering
    filter_used: Optional[bool]
    fallback_triggered: Optional[bool]
    filtering_reason: Optional[str]
