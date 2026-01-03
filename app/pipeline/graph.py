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
from app.nodes.metadata_filtering.node import metadata_filter_node

def router_logic(state: State):
    """
    Conditional edge logic for final generation.
    """
    if state.get("action") == "auto_reply":
        return "generate"
    return END

# Mapping of node names to their implementations
NODE_FUNCTIONS = {
    "classify": classify_node,
    "metadata_filter": metadata_filter_node,
    "expand_query": query_expansion_node,
    "retrieve": retrieve_node,
    "hybrid_search": hybrid_search_node,
    "rerank": rerank_node,
    "route": route_node,
    "generate": generate_node,
}

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "pipeline_config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# Build graph
workflow = StateGraph(State)

active_nodes = []
# 1. Add active nodes to the graph
for node_cfg in config.get("nodes", []):
    name = node_cfg["name"]
    enabled = node_cfg.get("enabled", False)
    
    if enabled and name in NODE_FUNCTIONS:
        workflow.add_node(name, NODE_FUNCTIONS[name])
        active_nodes.append(name)

# 2. Connect nodes sequentially (Linear Flow)
if not active_nodes:
    workflow.add_edge(START, END)
else:
    # START connection
    workflow.add_edge(START, active_nodes[0])
    
    for i in range(len(active_nodes) - 1):
        current_node = active_nodes[i]
        next_node = active_nodes[i+1]
        
        # Special logic for routing if it's in the middle
        if current_node == "route":
            # If 'generate' is in the pipeline, route can go to it
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
                # If generation is disabled, route just ends
                workflow.add_edge("route", END)
        else:
            # Standard linear edge
            workflow.add_edge(current_node, next_node)

    # Connect the last active node to END
    last_node = active_nodes[-1]
    # If the last node is 'route', its edges (conditional or END) are already added
    if last_node != "route":
        # Exception: 'generate' already has an implicit or explicit end in original logic?
        # We'll just add it for consistency.
        workflow.add_edge(last_node, END)

# Compile
rag_graph = workflow.compile()
