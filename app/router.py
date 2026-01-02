from typing import Literal

def decide_action(score: float, requires_handoff: bool, threshold: float) -> Literal["auto_reply", "handoff"]:
    """
    Decide whether to auto-reply or hand off to a human agent.
    
    Args:
        score: The similarity score of the best matched document.
        requires_handoff: Whether the matched document explicitly requires handoff.
        threshold: The confidence threshold for auto-reply.
        
    Returns:
        "auto_reply" or "handoff"
    """
    if requires_handoff:
        return "handoff"
    
    if score >= threshold:
        return "auto_reply"
    
    return "handoff"
