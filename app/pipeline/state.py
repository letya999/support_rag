from typing import TypedDict, List, Optional, Literal, Dict, Any

class State(TypedDict):
    question: str
    docs: List[str]
    answer: Optional[str]
    action: Optional[Literal["auto_reply", "handoff"]]
    confidence: Optional[float]
    matched_intent: Optional[str]
    matched_category: Optional[str]
    best_doc_metadata: Optional[Dict[str, Any]]

    # NEW: Classification results (Phase 3)
    intent: Optional[str]
    intent_confidence: Optional[float]
    category: Optional[str]
    category_confidence: Optional[float]
    all_category_scores: Optional[Dict[str, float]]

    # NEW: Filtering results (Phase 3)
    filter_used: Optional[bool]
    fallback_triggered: Optional[bool]
    filtering_reason: Optional[str]

    # NEW: Generation confidence scores (Phase 3)
    generation_confidence: Optional[float]
    faithfulness_score: Optional[float]
    relevancy_score: Optional[float]
