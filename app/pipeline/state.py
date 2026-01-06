from typing import TypedDict, List, Optional, Literal, Dict, Any, Annotated
import operator
from langgraph.graph import add_messages

def overwrite(left, right):
    return right

def keep_latest(existing: list | None, new: list | None) -> list:
    """Reducer: сохранять только последнюю версию."""
    return new if new is not None else existing

def merge_unique(existing: list | None, new: list | None) -> list:
    """Reducer: объединять уникальные элементы."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    seen = set()
    result = []
    for item in existing + new:
        key = item if isinstance(item, str) else str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

class State(TypedDict):
    question: Annotated[str, overwrite]
    user_id: Annotated[Optional[str], overwrite]
    session_id: Annotated[Optional[str], overwrite]
    
    # Lazy loaders
    user_profile: Annotated[Optional[Dict[str, Any]], overwrite]
    session_history: Annotated[Optional[List[Dict[str, Any]]], overwrite]
    _session_history_loader: Annotated[Optional[Any], overwrite]
    
    # Conversation History with LangGraph reducer
    conversation_history: Annotated[Optional[List[Dict[str, Any]]], add_messages]
    conversation_config: Annotated[Optional[Dict[str, Any]], overwrite]
    
    # Aggregation (Phase 2)
    aggregated_query: Annotated[Optional[str], overwrite]
    extracted_entities: Annotated[Optional[Dict[str, Any]], overwrite]
    
    # Query Translation (Phase 4)
    translated_query: Annotated[Optional[str], overwrite]  # Query translated to document language
    translation_performed: Annotated[Optional[bool], overwrite]
    
    queries: Annotated[Optional[List[str]], overwrite]
    
    # Reducers for docs and retrieval
    docs: Annotated[List[str], keep_latest]
    rerank_scores: Annotated[Optional[List[float]], overwrite]
    
    answer: Annotated[Optional[str], overwrite]
    action: Annotated[Optional[Literal["auto_reply", "handoff"]], overwrite]
    
    # Unified Classification
    confidence: Annotated[Optional[float], overwrite]
    category: Annotated[Optional[str], overwrite]  # Unified matched_category + semantic_category
    intent: Annotated[Optional[str], overwrite]
    
    # Legacy fields for backward compatibility (to be removed)
    matched_intent: Annotated[Optional[str], overwrite]
    matched_category: Annotated[Optional[str], overwrite]
    intent_confidence: Annotated[Optional[float], overwrite]
    category_confidence: Annotated[Optional[float], overwrite]
    semantic_intent: Annotated[Optional[str], overwrite]
    semantic_intent_confidence: Annotated[Optional[float], overwrite]
    semantic_category: Annotated[Optional[str], overwrite]
    semantic_category_confidence: Annotated[Optional[float], overwrite]
    semantic_time: Annotated[Optional[float], overwrite]

    best_doc_metadata: Annotated[Optional[Dict[str, Any]], overwrite]
    hybrid_used: Annotated[Optional[bool], overwrite]
    confidence_threshold: Annotated[Optional[float], overwrite]
    
    # Intermediate results for Fusion
    vector_results: Annotated[Optional[List[Any]], overwrite]
    lexical_results: Annotated[Optional[List[Any]], overwrite]
    
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
    cache_reason: Annotated[Optional[str], overwrite]  # "exact_match", "semantic_match"
    question_embedding: Annotated[Optional[List[float]], overwrite]  # Cached embedding for storage

    # Phase 3: State Machine
    dialog_state: Annotated[Optional[str], overwrite]
    attempt_count: Annotated[Optional[int], overwrite]
    state_behavior: Annotated[Optional[Dict[str, Any]], overwrite]
    dialog_analysis: Annotated[Optional[Dict[str, Any]], overwrite]
    
    # Phase 4: Prompt Routing & Localization
    system_prompt: Annotated[Optional[str], overwrite]
    generation_strategy: Annotated[Optional[str], overwrite]
    detected_language: Annotated[Optional[str], overwrite]
    language_confidence: Annotated[Optional[float], overwrite]
    
    # Phase 5 & 6: Safety, Emotion, Escalation (Analysis extensions)
    sentiment: Annotated[Optional[Dict[str, Any]], overwrite] # {label, score}
    safety_violation: Annotated[Optional[bool], overwrite]
    safety_reason: Annotated[Optional[str], overwrite]
    escalation_requested: Annotated[Optional[bool], overwrite]  # From dialog_analysis
    escalation_decision: Annotated[Optional[str], overwrite] # "escalate", "auto_reply"
    escalation_reason: Annotated[Optional[str], overwrite]
    action_recommendation: Annotated[Optional[str], overwrite] # "handoff", "auto_reply" from State Machine
    transition_source: Annotated[Optional[str], overwrite] # Debug: why state machine transitioned
    escalation_triggered: Annotated[Optional[bool], overwrite]  # True if escalation happened in routing
    escalation_message: Annotated[Optional[str], overwrite]  # User-facing message for escalation

