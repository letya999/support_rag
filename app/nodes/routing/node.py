from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.config.settings import settings
from app.nodes.routing.logic import decide_action
from app.observability.tracing import observe

class RoutingNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routing logic.
        """
        metadata = state.get("best_doc_metadata", {})
        confidence = state.get("confidence", 0.0)
        
        requires_handoff = metadata.get("requires_handoff", False)
        threshold = state.get("confidence_threshold")
        if threshold is None:
            threshold = metadata.get("confidence_threshold", settings.DEFAULT_CONFIDENCE_THRESHOLD)
        
        action = decide_action(confidence, requires_handoff, threshold)
        
        return {
            "action": action,
            "matched_intent": metadata.get("intent"),
            "matched_category": metadata.get("category")
        }

# For backward compatibility
route_node = RoutingNode()
