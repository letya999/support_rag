from typing import Dict, Any
from app.nodes.query_expansion.expander import QueryExpander
from app.observability.tracing import observe

@observe(as_type="span")
async def query_expansion_node(state: Dict[str, Any]):
    """
    LangGraph node for Query Expansion.
    Generates alternative queries to improve retrieval.
    """
    question = state.get("question", "")
    
    expander = QueryExpander()
    expanded_queries = await expander.expand(question)
    
    return {
        "queries": expanded_queries
    }
