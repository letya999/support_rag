from langgraph.graph import StateGraph, START, END
from app.pipeline.state import State
from app.nodes.retrieval.node import retrieve_node
from app.nodes.generation.node import generate_node
from app.nodes.routing.node import route_node

def router_logic(state: State):
    """
    Conditional edge logic.
    """
    if state["action"] == "auto_reply":
        return "generate"
    return END

# Build graph
workflow = StateGraph(State)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("route", route_node)
workflow.add_node("generate", generate_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "route")
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
