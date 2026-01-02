from typing import Dict, Any
from app.nodes.retrieval.search import retrieve_context
from app.observability.tracing import observe

@observe(as_type="span")
async def retrieve_node(state: Dict[str, Any]):
    """
    LangGraph node for retrieval.
    """
    question = state.get("question", "")
    output = await retrieve_context(question)
    
    return {
        "docs": output.docs,
        "confidence": output.confidence,
        "best_doc_metadata": output.best_doc_metadata
    }
