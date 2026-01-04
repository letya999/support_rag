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
    return "classify"  # This return value serves as the "cache miss" Edge Key

from app.nodes.multihop.node import multihop_node

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
    "generate": generate_node,
    "store_in_cache": store_in_cache_node,
    "load_session": load_session_node,
    "aggregate": aggregate_impl,
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

active_nodes = []
# 1. Add active nodes to the graph (excluding cache nodes which we handle separately)
for node_cfg in config.get("nodes", []):
    name = node_cfg["name"]
    enabled = node_cfg.get("enabled", False)

    if enabled and name in NODE_FUNCTIONS and name not in ["check_cache", "store_in_cache"]:
        workflow.add_node(name, NODE_FUNCTIONS[name])
        active_nodes.append(name)

# Ensure load_session is at the beginning if enabled
if "load_session" in active_nodes:
    active_nodes.remove("load_session")
    active_nodes.insert(0, "load_session")

# 2. Connect nodes with cache layer integration
if not active_nodes:
    if cache_enabled:
        # Only cache check -> END
        workflow.add_edge(START, "check_cache")
        workflow.add_conditional_edges(
            "check_cache",
            cache_hit_logic,
            {
                "store_in_cache": "store_in_cache",
                "classify": END  # No pipeline, just end
            }
        )
        workflow.add_edge("store_in_cache", END)
    else:
        workflow.add_edge(START, END)
else:
    # With pipeline nodes
    first_node = active_nodes[0]
    
    if cache_enabled:
        # START -> check_cache
        # If load_session is first, we might want START -> load_session -> check_cache ??
        # Or load_session effectively happens "before" the cache check contextually?
        # Actually session loading is needed probably BEFORE cache check to know user context?
        # Let's handle load_session as a distinct pre-step if present.
        
        start_target = "check_cache"
        
        if first_node == "load_session":
            # START -> load_session -> check_cache
            workflow.add_edge(START, "load_session")
            workflow.add_edge("load_session", "check_cache")
            # Remove load_session from the "pipeline after cache" list
            pipeline_nodes = active_nodes[1:]
        else:
            workflow.add_edge(START, "check_cache")
            pipeline_nodes = active_nodes

        # check_cache -> (cache hit) -> store_in_cache -> END
        #             -> (cache miss) -> first_pipeline_node
        
        if pipeline_nodes:
            miss_target = pipeline_nodes[0]
            workflow.add_conditional_edges(
                "check_cache",
                cache_hit_logic,
                {
                    "store_in_cache": "store_in_cache",
                    "classify": miss_target
                }
            )
            
             # Handle the pipeline connections
            for i in range(len(pipeline_nodes) - 1):
                current_node = pipeline_nodes[i]
                next_node = pipeline_nodes[i+1]

                # Special logic for routing if it's in the middle
                if current_node == "route":
                    if "generate" in pipeline_nodes:
                        workflow.add_conditional_edges(
                            "route",
                            router_logic,
                            {
                                "generate": "generate",
                                END: "store_in_cache"  # After generation, cache it
                            }
                        )
                    else:
                        workflow.add_edge("route", "store_in_cache")
                else:
                    workflow.add_edge(current_node, next_node)
            
            # Last node -> store_in_cache
            last_node = pipeline_nodes[-1]
            if last_node != "route":
                workflow.add_edge(last_node, "store_in_cache")
        else:
             # No pipeline nodes after cache check?
             workflow.add_conditional_edges(
                "check_cache",
                cache_hit_logic,
                {
                    "store_in_cache": "store_in_cache",
                    "classify": END 
                }
            )

        # store_in_cache -> END
        workflow.add_edge("store_in_cache", END)
    else:
        # No cache, original behavior
        workflow.add_edge(START, first_node)

        for i in range(len(active_nodes) - 1):
            current_node = active_nodes[i]
            next_node = active_nodes[i+1]

            if current_node == "route":
                if "generate" in active_nodes:
                    workflow.add_conditional_edges(
                        "route",
                        router_logic,
                        {
                            "generate": "generate",
                            END: END
                        }
                    )
                else:
                    workflow.add_edge("route", END)
            else:
                workflow.add_edge(current_node, next_node)

        last_node = active_nodes[-1]
        if last_node != "route":
            workflow.add_edge(last_node, END)

# Compile
rag_graph = workflow.compile()
