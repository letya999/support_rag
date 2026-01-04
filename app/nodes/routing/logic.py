"""
Routing decision logic.

Determines whether to auto_reply or handoff based on confidence
and various signals from the pipeline.
"""
from typing import Literal, Dict, Any


def decide_action(
    confidence: float, 
    requires_handoff: bool, 
    threshold: float,
    escalation_requested: bool = False,
    safety_violation: bool = False
) -> Literal["auto_reply", "handoff"]:
    """
    Decide the routing action based on multiple signals.
    
    Decision priority (highest to lowest):
    1. safety_violation -> always handoff
    2. escalation_requested -> handoff (user explicitly asked)
    3. requires_handoff -> handoff (document metadata)
    4. low confidence -> handoff
    5. default -> auto_reply
    
    Args:
        confidence: Confidence score from reranking/search
        requires_handoff: Flag from document metadata
        threshold: Minimum confidence for auto_reply
        escalation_requested: User requested human agent (from dialog_analysis)
        safety_violation: Safety check failed
        
    Returns:
        "auto_reply" or "handoff"
    """
    # Priority 1: Safety violation
    if safety_violation:
        return "handoff"
    
    # Priority 2: User explicitly requested escalation
    if escalation_requested:
        return "handoff"
    
    # Priority 3: Document requires handoff
    if requires_handoff:
        return "handoff"
    
    # Priority 4: Confidence check
    # Only check if threshold > 0 (allows disabling confidence check)
    if threshold > 0 and confidence < threshold:
        return "handoff"
    
    # Default: auto reply
    return "auto_reply"


def get_decision_reason(
    confidence: float,
    requires_handoff: bool,
    threshold: float,
    escalation_requested: bool = False,
    safety_violation: bool = False
) -> Dict[str, Any]:
    """
    Get detailed decision information for logging/debugging.
    
    Returns:
        Dict with action and reason
    """
    if safety_violation:
        return {"action": "handoff", "reason": "safety_violation", "priority": 1}
    
    if escalation_requested:
        return {"action": "handoff", "reason": "escalation_requested", "priority": 2}
    
    if requires_handoff:
        return {"action": "handoff", "reason": "requires_handoff", "priority": 3}
    
    if threshold > 0 and confidence < threshold:
        return {
            "action": "handoff", 
            "reason": "low_confidence",
            "priority": 4,
            "confidence": confidence,
            "threshold": threshold
        }
    
    return {"action": "auto_reply", "reason": "default", "priority": 5}
