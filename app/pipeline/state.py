from typing import TypedDict, List, Optional, Literal, Dict, Any, Annotated
import operator

def overwrite(left, right):
    return right

class State(TypedDict):
    question: Annotated[str, overwrite]
    user_id: Annotated[Optional[str], overwrite]
    session_id: Annotated[Optional[str], overwrite]
    user_profile: Annotated[Optional[Dict[str, Any]], overwrite]
    session_history: Annotated[Optional[List[Dict[str, Any]]], overwrite]
    conversation_config: Annotated[Optional[Dict[str, Any]], overwrite]
    
    # Aggregation (Phase 2)
    aggregated_query: Annotated[Optional[str], overwrite]
    extracted_entities: Annotated[Optional[Dict[str, Any]], overwrite]
    
    queries: Annotated[Optional[List[str]], overwrite]
    docs: Annotated[List[str], overwrite]
    rerank_scores: Annotated[Optional[List[float]], overwrite]
    answer: Annotated[Optional[str], overwrite]
    action: Annotated[Optional[Literal["auto_reply", "handoff"]], overwrite]
    confidence: Annotated[Optional[float], overwrite]
    matched_intent: Annotated[Optional[str], overwrite]
    matched_category: Annotated[Optional[str], overwrite]
    best_doc_metadata: Annotated[Optional[Dict[str, Any]], overwrite]
    hybrid_used: Annotated[Optional[bool], overwrite]
    confidence_threshold: Annotated[Optional[float], overwrite]
    
    # Intermediate results for Fusion
    vector_results: Annotated[Optional[List[Any]], overwrite]
    lexical_results: Annotated[Optional[List[Any]], overwrite]
    
    # Classification
    intent: Annotated[Optional[str], overwrite]
    intent_confidence: Annotated[Optional[float], overwrite]
    category: Annotated[Optional[str], overwrite]
    category_confidence: Annotated[Optional[float], overwrite]

    # FastText Classification (Testing)
    fasttext_intent: Annotated[Optional[str], overwrite]
    fasttext_intent_confidence: Annotated[Optional[float], overwrite]
    fasttext_category: Annotated[Optional[str], overwrite]
    fasttext_category_confidence: Annotated[Optional[float], overwrite]
    fasttext_time: Annotated[Optional[float], overwrite]
    
    # Filtering
    filter_used: Annotated[Optional[bool], overwrite]
    fallback_triggered: Annotated[Optional[bool], overwrite]
    filtering_reason: Annotated[Optional[str], overwrite]

    # Multi-hop Reasoning (Phase 3)
    complexity_level: Annotated[Optional[Literal["simple", "medium", "complex"]], overwrite]
    complexity_score: Annotated[Optional[float], overwrite]
    num_hops_required: Annotated[Optional[int], overwrite]
    primary_doc: Annotated[Optional[str], overwrite]
    related_docs: Annotated[Optional[List[str]], overwrite]
    hop_chain: Annotated[Optional[List[Dict[str, Any]]], overwrite]
    merged_context: Annotated[Optional[str], overwrite]
    multihop_used: Annotated[Optional[bool], overwrite]
    hops_performed: Annotated[Optional[int], overwrite]

    # Caching (Phase 2)
    cache_hit: Annotated[Optional[bool], overwrite]
    cache_key: Annotated[Optional[str], overwrite]
    cache_stats: Annotated[Optional[Dict[str, Any]], overwrite]

    # Phase 3: State Machine
    dialog_state: Annotated[Optional[str], overwrite]
    attempt_count: Annotated[Optional[int], overwrite]
    dialog_analysis: Annotated[Optional[Dict[str, Any]], overwrite]
    
    # Phase 4: Prompt Routing
    system_prompt: Annotated[Optional[str], overwrite]
    generation_strategy: Annotated[Optional[str], overwrite]
    
    # Phase 5 & 6: Safety, Emotion, Escalation (Analysis extensions)
    sentiment: Annotated[Optional[Dict[str, Any]], overwrite] # {label, score}
    safety_violation: Annotated[Optional[bool], overwrite]
    safety_reason: Annotated[Optional[str], overwrite]
    escalation_decision: Annotated[Optional[str], overwrite] # "escalate", "auto_reply"
    escalation_reason: Annotated[Optional[str], overwrite]
