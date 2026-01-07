from typing import List, Dict, Any
from app.observability.tracing import observe
from app.storage.models import SearchResult
from app.nodes.lexical_search.storage import lexical_search_db
from app.nodes.base_node import BaseNode

class LexicalSearchNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logic for lexical search.

        Contracts:
            - Required Inputs: `aggregated_query` OR `question` (str)
            - Optional Inputs: `detected_language` (str)
            - Guaranteed Outputs: `docs` (List[str]), `scores` (List[float]), `lexical_results` (List[SearchResult])
        """
        question = state.get("aggregated_query") or state.get("question", "")
        detected_language = state.get("detected_language")  # Get from language_detection node
        
        # For simplicity, we assume single query here. 
        # If we need multiple queries, we can expand it later.
        results = await lexical_search_db(
            question, 
            top_k=10,
            detected_language=detected_language
        )
        
        docs = [r.content for r in results]
        scores = [r.score for r in results]
        
        return {
            "docs": docs,
            "scores": scores,
            "lexical_results": results # For possible fusion later
        }

@observe(as_type="span")
async def lexical_search_node(
    query: str, 
    top_k: int = 10,
    detected_language: str = None
) -> List[SearchResult]:
    """
    Execute lexical search (BM25/FTS).
    
    Args:
        query: Search query
        top_k: Number of results to return
        detected_language: Optional language code from language_detection node
    """
    return await lexical_search_db(
        query, 
        top_k=top_k,
        detected_language=detected_language
    )

# For backward compatibility and graph integration
lexical_node = LexicalSearchNode()
