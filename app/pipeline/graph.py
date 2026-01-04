import json
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
from app.cache.nodes import check_cache_node, store_in_cache_node
from app.nodes.session_starter.node import load_session_node
from app.nodes.aggregation.lightweight import lightweight_aggregation_node
from app.nodes.aggregation.llm import llm_aggregation_node
from app.nodes.dialog_analysis.node import dialog_analysis_node
from app.nodes.state_machine.node import state_machine_node
from app.nodes.prompt_routing.node import route_prompt_node
from app.config.conversation_config import conversation_config

# Optional: Import multihop node if available (Phase 3)
try:
    from app.nodes.multihop.node import multihop_node
    MULTIHOP_AVAILABLE = True
except ImportError:
    MULTIHOP_AVAILABLE = False
    multihop_node = None

def cache_hit_logic(state: State):
    """
    Conditional edge logic for cache hits.
    If cache hit, skip to storing (or END).
    """
    if state.get("cache_hit", False):
        return "store_in_cache"
    return "miss"  # Return "miss" to proceed to pipeline

def router_logic(state: State):
    """
    Conditional edge logic for final generation.
    """
    if state.get("action") == "auto_reply":
        return "generate"
    return END

# Select aggregation implementation
aggregate_impl = llm_aggregation_node if conversation_config.use_llm_aggregation else lightweight_aggregation_node

# Mapping of node names to their implementations
NODE_FUNCTIONS = {
    "check_cache": check_cache_node,
    "fasttext_classify": fasttext_classify_node,
    "classify": classify_node,
    "metadata_filter": metadata_filter_node,
    "expand_query": query_expansion_node,
    "retrieve": retrieve_node,
    "hybrid_search": hybrid_search_node,
    "rerank": rerank_node,
    "multihop": multihop_node,
    "route": route_node,
    "route_prompt": route_prompt_node,
    "generate": generate_node,
    "store_in_cache": store_in_cache_node,
    "load_session": load_session_node,
    "aggregate": aggregate_impl,
    "analyze_dialog": dialog_analysis_node,
    "update_state": state_machine_node,
}

# Add multihop node if available (Phase 3)
if MULTIHOP_AVAILABLE:
    NODE_FUNCTIONS["multihop"] = multihop_node

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "pipeline_config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# Build graph
workflow = StateGraph(State)


# CACHE LAYER (Phase 2): Always add cache nodes
cache_enabled = config.get("cache", {}).get("enabled", True)
if cache_enabled:
    workflow.add_node("check_cache", NODE_FUNCTIONS["check_cache"])
    workflow.add_node("store_in_cache", NODE_FUNCTIONS["store_in_cache"])

# Identify active nodes
active_nodes_cfg = config.get("nodes", [])
active_node_names = [n["name"] for n in active_nodes_cfg if n.get("enabled", False)]

# Define Groups
state_machine_group = ["analyze_dialog", "update_state"]
rag_pipeline_group = ["aggregate", "fasttext_classify", "classify", "metadata_filter", "expand_query", "retrieve", "hybrid_search", "multihop", "rerank"]

# Add all active nodes to workflow
for name in active_node_names:
    if name in NODE_FUNCTIONS and name not in ["check_cache", "store_in_cache"]:
        workflow.add_node(name, NODE_FUNCTIONS[name])

# --- CONNECT EDGES ---

start_node = START

# 1. Load Session (Optional)
if "load_session" in active_node_names:
    workflow.add_edge(START, "load_session")
    if cache_enabled:
        workflow.add_edge("load_session", "check_cache")
        start_node = "check_cache" # Cache check is the divergent point
    else:
        start_node = "load_session"
elif cache_enabled:
    workflow.add_edge(START, "check_cache")
    start_node = "check_cache"

# 2. Sequential Logic Construction based on Config Order
# We follow `active_node_names` for sequence, but if `check_cache` exists, we inject the conditional edge.

# Filter nodes that are part of the pipeline (excluding load_session, check_cache, store_in_cache which we handled)
pipeline_nodes = [n for n in active_node_names if n not in ["load_session", "check_cache", "store_in_cache"]]

if pipeline_nodes:
    first_pipeline_node = pipeline_nodes[0]
    
    # Connect Start/Cache to Pipeline
    if cache_enabled:
        workflow.add_conditional_edges(
            "check_cache",
            cache_hit_logic,
            {
                "store_in_cache": "store_in_cache",
                "miss": first_pipeline_node
            }
        )
    elif start_node == START and "load_session" not in active_node_names:
        workflow.add_edge(START, first_pipeline_node)
    
    # Connect Pipeline Nodes sequentially
    for i in range(len(pipeline_nodes) - 1):
        current_node = pipeline_nodes[i]
        next_node = pipeline_nodes[i+1]

        # Special logic for routing if it's in the middle
        if current_node == "route":
            if "generate" in pipeline_nodes:
                # If prompt routing is enabled, route to it first
                target = "route_prompt" if "route_prompt" in active_node_names else "generate"
                
                workflow.add_conditional_edges(
                    "route",
                    router_logic,
                    {
                        "generate": target,
                        END: "store_in_cache" if cache_enabled else END
                    }
                )
            else:
                 workflow.add_edge("route", "store_in_cache" if cache_enabled else END)
        else:
            workflow.add_edge(current_node, next_node)
            
    # Handle End of Pipeline
    last_node = pipeline_nodes[-1]
    if last_node != "route": # Route handles its own exit
         if cache_enabled:
             workflow.add_edge(last_node, "store_in_cache")
         else:
             workflow.add_edge(last_node, END)
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
    else:
        pass # Empty graph

# Cache Store always goes to END
if cache_enabled:
    workflow.add_edge("store_in_cache", END)

# Compile
rag_graph = workflow.compile()
