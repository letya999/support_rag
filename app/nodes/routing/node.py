"""
Routing Node.

Final routing decision: auto_reply or handoff.
Considers confidence, escalation requests, and document requirements.
"""
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.settings import settings
from app.nodes.routing.logic import decide_action, get_decision_reason
from app.observability.tracing import observe

# Default config values
DEFAULT_MIN_CONFIDENCE = 0.3


def _get_params() -> Dict[str, Any]:
    """Get node parameters from centralized config."""
    try:
        from app.services.config_loader.loader import get_node_params
        return get_node_params("routing")
    except Exception:
        return {}


class RoutingNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routing logic with confidence handling.
        Respects min_confidence, escalation_requested, and requires_handoff.
        """
        params = _get_params()
        min_confidence = params.get("min_confidence_auto_reply", DEFAULT_MIN_CONFIDENCE)
        respect_escalation = params.get("respect_escalation_decision", True)
        respect_handoff = params.get("respect_requires_handoff", True)
        
        # Get signals from state
        metadata = state.get("best_doc_metadata", {})
        confidence = state.get("confidence", 0.0)
        
        # Determine threshold
        threshold = state.get("confidence_threshold")
        if threshold is None:
            threshold = metadata.get("confidence_threshold", min_confidence)
        
        # Get escalation signal from dialog_analysis
        escalation_requested = False
        if respect_escalation:
            escalation_requested = state.get("escalation_requested", False)
        
        # Get requires_handoff from document metadata
        requires_handoff = False
        if respect_handoff:
            requires_handoff = metadata.get("requires_handoff", False)
        
        # Safety violation (if present)
        safety_violation = state.get("safety_violation", False)
        
        # Make decision
        action = decide_action(
            confidence=confidence,
            requires_handoff=requires_handoff,
            threshold=threshold,
            escalation_requested=escalation_requested,
            safety_violation=safety_violation
        )
        
        # Get decision details for logging
        decision_info = get_decision_reason(
            confidence=confidence,
            requires_handoff=requires_handoff,
            threshold=threshold,
            escalation_requested=escalation_requested,
            safety_violation=safety_violation
        )
        
        return {
            "action": action,
            "matched_intent": metadata.get("intent"),
            "matched_category": metadata.get("category"),
            "routing_reason": decision_info.get("reason"),
            "routing_confidence": confidence,
            "routing_threshold": threshold
        }


# For backward compatibility
route_node = RoutingNode()
