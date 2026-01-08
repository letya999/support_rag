"""
RAG Pipeline Graph Builder

Constructs the LangGraph workflow based on YAML configuration.
Migrated from JSON to YAML for better readability and comments support.
"""
import yaml
import os
from langgraph.graph import StateGraph, START, END
from app.pipeline.state import State
from app.nodes.retrieval.node import retrieve_node
from app.nodes.generation.node import generate_node
from app.nodes.routing.node import route_node
from app.nodes.query_expansion.node import query_expansion_node
from app.nodes.reranking.node import rerank_node
from app.nodes.hybrid_search.node import hybrid_search_node
from app.nodes.classification.node import classify_node
from app.nodes.easy_classification.node import fasttext_classify_node
from app.nodes.metadata_filtering.node import metadata_filter_node
# New cache nodes from refactored structure
from app.nodes.check_cache.node import check_cache_node
from app.nodes.store_in_cache.node import store_in_cache_node
from app.nodes.cache_similarity.node import cache_similarity_node
from app.nodes.session_starter.node import load_session_node
from app.nodes.aggregation.node import aggregate_node
from app.nodes.dialog_analysis.node import dialog_analysis_node
from app.nodes.state_machine.node import state_machine_node
from app.nodes.prompt_routing.node import route_prompt_node
from app.nodes.lexical_search.node import lexical_node
from app.nodes.fusion.node import fusion_node
from app.nodes.archive_session.node import archive_session_node
from app.nodes.language_detection.node import language_detection_node
from app.nodes.query_translation.node import query_translation_node
from app.nodes.input_guardrails.node import input_guardrails_node
from app.nodes.output_guardrails.node import output_guardrails_node
from app.pipeline.config_proxy import conversation_config
from app.services.config_loader.loader import load_pipeline_config, get_node_enabled, get_cache_config
from app.pipeline.schema_generator import generate_node_schema

# Optional: Import multihop node if available
try:
    from app.nodes.multihop.node import multihop_node
    MULTIHOP_AVAILABLE = True
except ImportError:
    MULTIHOP_AVAILABLE = False
    multihop_node = None


# --- NODE NAMING ---
# All node names must match their folder names for config loading to work correctly.
# Mapping of node names (matching folder names) to their implementations

NODE_FUNCTIONS = {
    "check_cache": check_cache_node,
    "cache_similarity": cache_similarity_node,  # NEW: Optional semantic similarity check
    "easy_classification": fasttext_classify_node,  # Folder: easy_classification/
    "classify": classify_node,
    "metadata_filtering": metadata_filter_node,     # Folder: metadata_filtering/
    "expand_query": query_expansion_node,
    "retrieve": retrieve_node,
    "hybrid_search": hybrid_search_node,
    "reranking": rerank_node,                       # Folder: reranking/
    "multihop": multihop_node,
    "routing": route_node,                          # Folder: routing/
    "generation": generate_node,                    # Folder: generation/
    "store_in_cache": store_in_cache_node,
    "session_starter": load_session_node,
    "aggregation": aggregate_node,                  # Folder: aggregation/
    "dialog_analysis": dialog_analysis_node,
    "state_machine": state_machine_node,
    "prompt_routing": route_prompt_node,
    "lexical_search": lexical_node,
    "fusion": fusion_node,
    "archive_session": archive_session_node,
    "language_detection": language_detection_node,
    "query_translation": query_translation_node,    # Folder: query_translation/
    "input_guardrails": input_guardrails_node,
    "output_guardrails": output_guardrails_node,
}

# Add multihop node if available
if MULTIHOP_AVAILABLE:
    NODE_FUNCTIONS["multihop"] = multihop_node


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
    Early exit logic после dialog_analysis.
    
    Если есть критические сигналы (safety_violation или escalation_requested),
    пропускаем поиск и сразу идем в state_machine для быстрой эскалации.
    
    Returns:
        "fast_escalate" - пропустить поиск, сразу в state_machine
        "continue" - обычный поток через aggregation → search → state_machine
    """
    # Guardrails blocked - pass to state_machine immediately
    if state.get("guardrails_blocked", False):
         return "fast_escalate"

    # Критическая эскалация - сразу в state_machine без поиска
    if state.get("safety_violation", False):
        print("⚡ Fast escalation: safety_violation detected")
        return "fast_escalate"
    
    if state.get("escalation_requested", False):
        print("⚡ Fast escalation: user requested operator")
        return "fast_escalate"
    
    # Default: continue normal pipeline flow
    return "continue"


def check_guardrails_outcome(state: State):
    """
    Conditional edge logic for input_guardrails.
    Determines whether to proceed or block based on guardrails output.
    """
    if state.get("guardrails_blocked"):
        return "blocked"
    return "continue"


# Build graph
workflow = StateGraph(State)

# CACHE LAYER: Always add cache nodes if enabled
cache_enabled = get_node_enabled("check_cache")
if cache_enabled:
    # Generate schemas for cache nodes
    check_cache_schema = generate_node_schema("check_cache", NODE_FUNCTIONS["check_cache"])
    store_cache_schema = generate_node_schema("store_in_cache", NODE_FUNCTIONS["store_in_cache"])
    
    workflow.add_node("check_cache", NODE_FUNCTIONS["check_cache"], input_schema=check_cache_schema)
    workflow.add_node("store_in_cache", NODE_FUNCTIONS["store_in_cache"], input_schema=store_cache_schema)

# Get pipeline nodes from config
config = load_pipeline_config()
pipeline_config = config.get("pipeline", config.get("nodes", []))

# Identify active nodes preserving config order
active_node_names = [
    n["name"] for n in pipeline_config 
    if n.get("enabled", False)
]

# Add all active nodes to workflow

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

# Add all active nodes to workflow
print(f"DEBUG: Active config nodes: {active_node_names}")
validate_pipeline_structure(active_node_names)

for name in active_node_names:
    if name in NODE_FUNCTIONS and name not in ["check_cache", "store_in_cache"]:
        print(f"DEBUG: Adding node {name}")
        # Generate schema for this node
        node_schema = generate_node_schema(name, NODE_FUNCTIONS[name])
        workflow.add_node(name, NODE_FUNCTIONS[name], input_schema=node_schema)
    elif name not in NODE_FUNCTIONS:
        print(f"DEBUG: Warning: Node {name} enabled in config but missing in NODE_FUNCTIONS")

# --- CONNECT EDGES ---

start_node = START

# --- SECURITY: input_guardrails MUST run BEFORE cache check ---
# This prevents malicious content from bypassing safety checks via cache hits

input_guardrails_enabled = "input_guardrails" in active_node_names

# 1. Load Session (Optional)
if "session_starter" in active_node_names:
    workflow.add_edge(START, "session_starter")
    # After session: guardrails first, then cache
    if input_guardrails_enabled:
        workflow.add_edge("session_starter", "input_guardrails")
        start_node = "input_guardrails"
    elif cache_enabled:
        workflow.add_edge("session_starter", "check_cache")
        start_node = "check_cache"
    else:
        start_node = "session_starter"
elif input_guardrails_enabled:
    workflow.add_edge(START, "input_guardrails")
    start_node = "input_guardrails"
elif cache_enabled:
    workflow.add_edge(START, "check_cache")
    start_node = "check_cache"

# Filter nodes that are part of the main pipeline
# IMPORTANT: input_guardrails is now handled separately (before cache)
pipeline_nodes = [
    n for n in active_node_names 
    if n not in ["session_starter", "check_cache", "store_in_cache", "archive_session", "input_guardrails"]
]

if pipeline_nodes:
    first_pipeline_node = pipeline_nodes[0]
    
    # Connect input_guardrails → cache (if not blocked) or state_machine (if blocked)
    if input_guardrails_enabled:
        if cache_enabled:
            # Connect input_guardrails → cache (if not blocked) or state_machine (if blocked)
            workflow.add_conditional_edges(
                "input_guardrails",
                check_guardrails_outcome,
                {
                    "blocked": "state_machine" if "state_machine" in active_node_names else first_pipeline_node,
                    "continue": "check_cache"
                }
            )
            # Cache logic remains the same
            workflow.add_conditional_edges(
                "check_cache",
                cache_hit_logic,
                {
                    "store_in_cache": "store_in_cache",
                    "miss": first_pipeline_node
                }
            )
        else:
            # No cache, guardrails goes to first pipeline node or state_machine if blocked
            workflow.add_conditional_edges(
                "input_guardrails",
                check_guardrails_outcome,
                {
                    "blocked": "state_machine" if "state_machine" in active_node_names else first_pipeline_node,
                    "continue": first_pipeline_node
                }
            )
    elif cache_enabled:
        # No guardrails, just cache
        workflow.add_conditional_edges(
            "check_cache",
            cache_hit_logic,
            {
                "store_in_cache": "store_in_cache",
                "miss": first_pipeline_node
            }
        )
    elif start_node == START and "session_starter" not in active_node_names:
        workflow.add_edge(START, first_pipeline_node)
    
    # Connect Pipeline Nodes sequentially
    for i in range(len(pipeline_nodes) - 1):
        current_node = pipeline_nodes[i]
        next_node = pipeline_nodes[i+1]

        # NOTE: input_guardrails is now handled BEFORE cache check (see above)
        # so we don't need special handling here anymore
        
        # Special logic: Early exit после dialog_analysis
        if current_node == "dialog_analysis" and "state_machine" in active_node_names:
            # Находим следующий узел после dialog_analysis (обычно aggregation или state_machine)
            normal_next_node = next_node
            
            # Добавляем conditional edge
            workflow.add_conditional_edges(
                "dialog_analysis",
                should_fast_escalate,
                {
                    "fast_escalate": "state_machine",  # Быстрая эскалация
                    "continue": normal_next_node        # Обычный поток
                }
            )
        # Special logic for routing if it's in the middle
        elif current_node == "routing":
            if "generation" in pipeline_nodes:
                # If prompt routing is enabled, route to it first
                target = "prompt_routing" if "prompt_routing" in active_node_names else "generation"
                target_exit = "archive_session" if "archive_session" in active_node_names else ("store_in_cache" if cache_enabled else END)
                
                workflow.add_conditional_edges(
                    "routing",
                    router_logic,
                    {
                        "generation": target,
                        END: target_exit
                    }
                )
            else:
                target_exit = "archive_session" if "archive_session" in active_node_names else ("store_in_cache" if cache_enabled else END)
                workflow.add_edge("routing", target_exit)
        # Special logic: state_machine должен идти в routing
        elif current_node == "state_machine" and "routing" in active_node_names:
            workflow.add_edge("state_machine", "routing")
        else:
            workflow.add_edge(current_node, next_node)

            
    # Handle End of Pipeline
    last_node = pipeline_nodes[-1]
    if last_node != "routing":
        if "archive_session" in active_node_names:
            workflow.add_edge(last_node, "archive_session")
        elif cache_enabled:
            workflow.add_edge(last_node, "store_in_cache")
        else:
            workflow.add_edge(last_node, END)
              
    # Ensure archive_session has an exit path
    if "archive_session" in active_node_names:
        if cache_enabled:
            workflow.add_edge("archive_session", "store_in_cache")
        else:
            workflow.add_edge("archive_session", END)
else:
    # No pipeline nodes
    if cache_enabled:
        workflow.add_conditional_edges(
            "check_cache",
            cache_hit_logic,
            {
                "store_in_cache": "store_in_cache",
                "miss": END 
            }
        )

# Cache Store always goes to END
if cache_enabled:
    workflow.add_edge("store_in_cache", END)

# Compile
rag_graph = workflow.compile()
