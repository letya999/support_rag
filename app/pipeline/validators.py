"""
Validators for RAG Pipeline Structure.
"""

def validate_pipeline_structure(active_nodes: list[str]):
    """
    Validate the pipeline structure against critical dependencies.
    Raises ValueError if invalid.
    """
    # 1. Fusion Requirements
    if "fusion" in active_nodes:
        missing = []
        if "retrieve" not in active_nodes:
            missing.append("retrieve")
        if "lexical_search" not in active_nodes:
            missing.append("lexical_search")
        
        if missing:
             raise ValueError(f"CRITICAL: 'fusion' node requires {missing} to be enabled. Fusion lacks graceful degradation.")

    # 2. Critical Order Dependencies
    def check_order(first: str, second: str):
        if first in active_nodes and second in active_nodes:
            idx1 = active_nodes.index(first)
            idx2 = active_nodes.index(second)
            if idx1 > idx2:
                raise ValueError(f"CRITICAL: '{first}' must execute before '{second}'. Current order: {active_nodes}") 

    # Check Critical Pairs if both exist
    check_order("retrieve", "fusion")
    check_order("lexical_search", "fusion")
    check_order("reranking", "state_machine") # State machine needs confidence
    check_order("state_machine", "routing")   # Routing acts on state machine decision
    check_order("routing", "generation")      # Routing controls flow to generation
