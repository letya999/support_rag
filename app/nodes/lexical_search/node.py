from typing import List, Dict, Any, Optional
from app.observability.tracing import observe
from app.storage.models import SearchResult
from app.storage.lexical_operations import lexical_search_db
from app.nodes.base_node import BaseNode

class LexicalSearchNode(BaseNode):
    """
    Performs lexical search using BM25/Full-Text Search.
    
    Contracts:
        Input:
            Required: None
            Optional:
                - question (str): User question
                - aggregated_query (str): Enhanced query
                - detected_language (str): User's language
        
        Output:
            Guaranteed:
                - docs (List[str]): Retrieved document contents
                - scores (List[float]): BM25 scores
                - lexical_results (List[SearchResult]): Raw results
            Conditional: None
    """
    
    INPUT_CONTRACT = {
        "required": [],
        "optional": ["question", "aggregated_query", "detected_language"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["docs", "scores", "lexical_results"],
        "conditional": []
    }
    
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
    detected_language: Optional[str] = None,
    category_filter: Optional[str] = None
) -> List[SearchResult]:
    """
    Execute lexical search (BM25/FTS).
    
    Args:
        query: Search query
        top_k: Number of results to return
        detected_language: Optional language code from language_detection node
        category_filter: Optional category to filter documents by (controlled by config)
    """
    return await lexical_search_db(
        query, 
        top_k=top_k,
        detected_language=detected_language,
        category_filter=category_filter
    )

# For backward compatibility and graph integration
lexical_node = LexicalSearchNode()
