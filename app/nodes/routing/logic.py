from typing import Literal

def decide_action(score: float, requires_handoff: bool, threshold: float) -> Literal["auto_reply", "handoff"]:
    if requires_handoff:
        return "handoff"
    
    if score >= threshold:
        return "auto_reply"
    
    return "handoff"
