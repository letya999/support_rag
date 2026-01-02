from typing import Dict, Any, Literal
from app.config.settings import settings
from app.nodes.routing.logic import decide_action
from app.observability.tracing import observe

@observe(as_type="span")
async def route_node(state: Dict[str, Any]):
    """
    Routing node.
    """
    metadata = state.get("best_doc_metadata", {})
    confidence = state.get("confidence", 0.0)
    
    requires_handoff = metadata.get("requires_handoff", False)
    # Allow threshold override from state (highest priority), metadata, or use default
    threshold = state.get("confidence_threshold")
    if threshold is None:
        threshold = metadata.get("confidence_threshold", settings.DEFAULT_CONFIDENCE_THRESHOLD)
    
    action = decide_action(confidence, requires_handoff, threshold)
    
    return {
        "action": action,
        "matched_intent": metadata.get("intent"),
        "matched_category": metadata.get("category")
    }
