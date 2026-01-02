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
    if state["action"] == "auto_reply":
        return "generate"
    return END

def retrieval_router(state: State):
    """
    Route to hybrid or simple vector search.
    """
    if state.get("hybrid_used"):
        return "hybrid_search"
    return "retrieve"

# Build graph
workflow = StateGraph(State)
workflow.add_node("classify", classify_node)
workflow.add_node("metadata_filter", metadata_filter_node)
workflow.add_node("expand_query", query_expansion_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("hybrid_search", hybrid_search_node)
workflow.add_node("rerank", rerank_node)
workflow.add_node("route", route_node)
workflow.add_node("generate", generate_node)

workflow.add_edge(START, "classify")
workflow.add_edge("classify", "metadata_filter")
workflow.add_edge("metadata_filter", "expand_query")

# Conditional routing after expansion
workflow.add_conditional_edges(
    "expand_query",
    retrieval_router,
    {
        "hybrid_search": "hybrid_search",
        "retrieve": "retrieve" 
    }
)

# Both retrieval paths go to rerank
workflow.add_edge("retrieve", "rerank")
workflow.add_edge("hybrid_search", "rerank")

workflow.add_edge("rerank", "route")
workflow.add_conditional_edges(
    "route",
    router_logic,
    {
        "generate": "generate",
        END: END
    }
)
workflow.add_edge("generate", END)

# Compile
rag_graph = workflow.compile()
