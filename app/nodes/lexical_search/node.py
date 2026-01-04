from typing import List, Dict, Any
from app.observability.tracing import observe
from app.storage.models import SearchResult
from app.nodes.lexical_search.storage import lexical_search_db
from app.nodes.base_node import BaseNode

class LexicalSearchNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logic for lexical search.
        """
        question = state.get("aggregated_query") or state.get("question", "")
        # For simplicity, we assume single query here. 
        # If we need multiple queries, we can expand it later.
        results = await lexical_search_db(question, top_k=10)
        
        docs = [r.content for r in results]
        scores = [r.score for r in results]
        
        return {
            "docs": docs,
            "scores": scores,
            "lexical_results": results # For possible fusion later
        }

@observe(as_type="span")
async def lexical_search_node(query: str, top_k: int = 10) -> List[SearchResult]:
    """
    Execute lexical search (BM25/FTS).
    """
    return await lexical_search_db(query, top_k=top_k)

# For backward compatibility and graph integration
lexical_node = LexicalSearchNode()
