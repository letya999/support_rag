"""
Routing Logic functions for Conditional Edges in the RAG Pipeline.
"""
from langgraph.graph import END
from app.pipeline.state import State

def cache_hit_logic(state: State):
    """
    Conditional edge logic for cache hits.
    If cache hit, skip to storing (or END).
    """
    if state.get("cache_hit", False):
        return "store_in_cache"
    return "miss"

def router_logic(state: State):
    """
    Conditional edge logic for final generation.
    """
    if state.get("action") == "auto_reply":
        return "generation"
    return END

def should_fast_escalate(state: State):
    """
    Early exit logic after dialog_analysis.
    
    If critical signals (safety_violation or escalation_requested) are present,
    skip search and go immediately to state_machine.
    
    Returns:
        "fast_escalate" - skip search, immediate state_machine
        "continue" - normal flow
    """
    # Guardrails blocked - pass to state_machine immediately
    if state.get("guardrails_blocked", False):
         return "fast_escalate"

    # Critical escalation - fast track
    if state.get("safety_violation", False):
        print("⚡ Fast escalation: safety_violation detected")
        return "fast_escalate"
    
    if state.get("escalation_requested", False):
        print("⚡ Fast escalation: user requested operator")
        return "fast_escalate"
    
    return "continue"

def check_guardrails_outcome(state: State):
    """
    Conditional edge logic for input_guardrails.
    Determines whether to proceed or block based on guardrails output.
    """
    if state.get("guardrails_blocked"):
        return "blocked"
    return "continue"
