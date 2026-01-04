from typing import Dict, Any
from app.pipeline.state import State
from app.observability.tracing import observe
from app.nodes.state_machine.states_config import TRANSITION_RULES, STATE_CONFIG, INITIAL, ANSWER_PROVIDED, ESCALATION_NEEDED, ESCALATION_REQUESTED

@observe(as_type="span")
def state_machine_node(state: State) -> Dict[str, Any]:
    """
    Main State Machine node.
    Updates the session state based on dialog analysis signals and explicit rules.
    """
    
    # Inputs
    analysis = state.get("dialog_analysis", {})
    current_state = state.get("dialog_state", INITIAL)
    attempt_count = state.get("attempt_count", 0)
    sentiment = state.get("sentiment", {})
    escalation_decision = state.get("escalation_decision", "auto_reply")
    
    if current_state is None:
        current_state = INITIAL
    if attempt_count is None:
        attempt_count = 0
    
    new_state = current_state
    
    # ---------------------------------------------------------
    # 1. Critical Override: Phase 6 Escalation Decision
    # ---------------------------------------------------------
    if escalation_decision == "escalate":
        if analysis.get("escalation_requested"):
            return {
                "dialog_state": ESCALATION_REQUESTED,
                "attempt_count": attempt_count
            }
        else:
            return {
                "dialog_state": ESCALATION_NEEDED,
                "attempt_count": attempt_count
            }

    # ---------------------------------------------------------
    # 2. Rule-Based Match (Iterate by priority)
    # ---------------------------------------------------------
    rule_matched_state = None
    
    # Sort by priority just in case (though list is ordered)
    sorted_rules = sorted(TRANSITION_RULES, key=lambda x: x["priority"])
    
    for rule in sorted_rules:
        field = rule["condition_field"]
        value = rule["condition_value"]
        target = rule["target_state"]
        
        # Check if analysis has this field and it matches value
        if analysis.get(field) == value:
            rule_matched_state = target
            break # Stop at highest priority match
            
    # Required State Logic (Transitions based on previous state)
    if rule_matched_state:
        # Handle specific transitions that depend on history
        
        if rule_matched_state == ANSWER_PROVIDED:
            # If we were already providing answers, increment attempt
            # Exception: if we were RESOLVED and user asks again -> New topic, reset count
            if current_state == "RESOLVED":
                attempt_count = 1
            else:
                attempt_count += 1
        
        # If we just went to resolved, reset attempts? No, keep history for now.
        
        new_state = rule_matched_state

    # ---------------------------------------------------------
    # 3. Dynamic logic (Thresholds & Counters)
    # ---------------------------------------------------------
    
    # Check max attempts limit
    if new_state == ANSWER_PROVIDED and attempt_count > STATE_CONFIG["max_attempts"]:
        if STATE_CONFIG["escalate_on_max_attempts"]:
            new_state = ESCALATION_NEEDED

    return {
        "dialog_state": new_state,
        "attempt_count": attempt_count
    }
