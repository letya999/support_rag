import logging

logger = logging.getLogger(__name__)

def route_after_retrieval(state):
    """
    Route to clarification if needed, else to next step.
    Checks 'dialog_state' and falls back to checking 'best_doc_metadata' directly.
    """
    dialog_state = state.get("dialog_state")
    best_metadata = state.get("best_doc_metadata", {})
    has_questions = bool(best_metadata.get("clarifying_questions"))

    logger.debug(f"Routing check: dialog_state='{dialog_state}', has_questions={has_questions}")

    # Primary check: Dialog State
    if dialog_state == "NEEDS_CLARIFICATION":
        return "clarification_questions"
    
    # Fallback: If metadata implies clarification but state missed it
    if has_questions:
        logger.warning("Dialog state check failed but metadata contains clarifying questions. Routing to clarification.")
        return "clarification_questions"
        
    return "continue"

def check_guardrails_and_clarification(state):
    """
    Combined routing logic:
    1. Guardrails check (Priority 1)
    2. Active Clarification Mode check (Priority 2)
    3. Standard Flow (Priority 3)
    """
    if state.get("guardrails_blocked"):
        return "blocked"
    
    # Check if we are in the middle of a clarification loop
    # We must bypass search to avoid hallucinations (e.g. searching for "12")
    ctx = state.get("clarification_context")
    if ctx and ctx.get("active"):
        return "clarification_mode"
        
    return "continue"
