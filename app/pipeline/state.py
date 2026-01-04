from typing import TypedDict, List, Optional, Literal, Dict, Any

class State(TypedDict):
    question: str
    user_id: Optional[str]
    session_id: Optional[str]
    user_profile: Optional[Dict[str, Any]]
    session_history: Optional[List[Dict[str, Any]]]
    conversation_config: Optional[Dict[str, Any]]
    
    # Aggregation (Phase 2)
    aggregated_query: Optional[str]
    extracted_entities: Optional[Dict[str, Any]]
    
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
    confidence_threshold: Optional[float]
    
    # Classification
    intent: Optional[str]
    intent_confidence: Optional[float]
    category: Optional[str]
    category_confidence: Optional[float]

    # FastText Classification (Testing)
    fasttext_intent: Optional[str]
    fasttext_intent_confidence: Optional[float]
    fasttext_category: Optional[str]
    fasttext_category_confidence: Optional[float]
    fasttext_time: Optional[float]
    
    # Filtering
    filter_used: Optional[bool]
    fallback_triggered: Optional[bool]
    filtering_reason: Optional[str]

    # Multi-hop Reasoning (Phase 3)
    complexity_level: Optional[str]  # "simple", "medium", "complex"
    complexity_score: Optional[float]
    num_hops_required: Optional[int]
    primary_doc: Optional[str]
    related_docs: Optional[List[str]]
    hop_chain: Optional[List[str]]
    merged_context: Optional[str]
    multihop_used: Optional[bool]
    hops_performed: Optional[int]

    # Caching (Phase 2)
    cache_hit: Optional[bool]
    cache_key: Optional[str]
    cache_stats: Optional[Dict[str, Any]]
    # Multi-hop
    complexity_level: Optional[Literal["simple", "medium", "complex"]]
    complexity_score: Optional[float]
    num_hops_required: Optional[int]
    primary_doc: Optional[str]
    related_docs: List[str]
    hop_chain: Optional[List[dict]]
    merged_context: Optional[str]
    multihop_used: Optional[bool]
    hops_performed: Optional[int]
