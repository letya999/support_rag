from typing import Dict, Any
from app.pipeline.state import State
from app.observability.tracing import observe

@observe(as_type="span")
def session_update_node(state: State) -> Dict[str, Any]:
    """
    Updates the session state based on dialog analysis.
    Deterministic state machine suitable for running in a branch.
    """
    
    # Inputs
    analysis = state.get("dialog_analysis", {})
    current_state = state.get("dialog_state", "INITIAL")
    attempt_count = state.get("attempt_count", 0)
    if current_state is None:
        current_state = "INITIAL"
    if attempt_count is None:
        attempt_count = 0
    
    # Logic
    new_state = current_state
    
    # 1. Human Requested -> Highest Priority
    if analysis.get("escalation_requested"):
        new_state = "ESCALATION_REQUESTED"
    
    # 2. Gratitude -> Resolved
    elif analysis.get("is_gratitude"):
        new_state = "RESOLVED"
    
    # 3. Repeated Question -> Increment Attempt, set state
    elif analysis.get("repeated_question"):
        attempt_count += 1
        new_state = "ANSWER_PROVIDED" # Re-answering
        
    # 4. Normal Question Flow
    elif analysis.get("is_question"):
        if current_state == "INITIAL":
            new_state = "ANSWER_PROVIDED"
            attempt_count = 1
        elif current_state == "RESOLVED":
            # New question after resolution -> New flow
            new_state = "ANSWER_PROVIDED"
            attempt_count = 1
        elif current_state == "ANSWER_PROVIDED":
            # Follow up question
            attempt_count += 1
            
    # 5. Frustration -> Signal for Escalation (Soft)
    if analysis.get("frustration_detected"):
         # If frustrated AND already answered once -> Escalate needed
         if attempt_count > 0:
             new_state = "ESCALATION_NEEDED"

    return {
        "dialog_state": new_state,
        "attempt_count": attempt_count
    }
