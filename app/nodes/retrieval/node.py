from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
from app.nodes.retrieval.search import retrieve_context
from app.observability.tracing import observe

class RetrievalNode(BaseNode):
    """
    Retrieves relevant documents using vector search.
    
    Contracts:
        Input:
            Required: None (uses aggregated_query or question)
            Optional:
                - aggregated_query (str): Enhanced query
                - question (str): Original question
                - matched_category (str): Category filter
                - filter_used (bool): Whether to apply filter
        
        Output:
            Guaranteed:
                - docs (List[str]): Retrieved document contents
                - scores (List[float]): Relevance scores
                - confidence (float): Top score as confidence
                - best_doc_metadata (Dict): Metadata of best document
            Conditional:
                - vector_results (List[SearchResult]): Raw search results
    """
    
    INPUT_CONTRACT = {
        "required": [],
        "optional": ["aggregated_query", "question", "matched_category", "filter_used"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["docs", "scores", "confidence", "best_doc_metadata"],
        "conditional": ["vector_results"]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logic for simple retrieval.

        Contracts:
            - Required Inputs: `aggregated_query` OR `question` (str)
            - Optional Inputs: `matched_category` (str)
            - Guaranteed Outputs: `docs` (List[str]), `scores` (List[float]), `confidence` (float), `best_doc_metadata` (Dict), `vector_results` (List[SearchResult])
        """
        question = state.get("aggregated_query") or state.get("question", "")
        category_filter = state.get("matched_category") if state.get("filter_used") else None
        output = await retrieve_context(question, category_filter=category_filter)
        
        return {
            "docs": output.docs,
            "scores": output.scores,
            "confidence": output.confidence,
            "best_doc_metadata": output.best_doc_metadata,
            "vector_results": output.vector_results
        }

class RetrievalExpandedNode(BaseNode):
    """
    Retrieves documents using multiple expanded queries.
    
    Contracts:
        Input:
            Required: None
            Optional:
                - aggregated_query (str): Enhanced query
                - question (str): Original question
                - queries (List[str]): Expanded queries
        
        Output:
            Guaranteed:
                - docs (List[str]): Retrieved document contents
                - scores (List[float]): Relevance scores
                - confidence (float): Top score
                - best_doc_metadata (Dict): Metadata of best document
            Conditional:
                - vector_results (List[SearchResult]): Raw results
    """
    
    INPUT_CONTRACT = {
        "required": [],
        "optional": ["aggregated_query", "question", "queries"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["docs", "scores", "confidence", "best_doc_metadata"],
        "conditional": ["vector_results"]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logic for expanded retrieval (multiple queries).
        """
        question = state.get("aggregated_query") or state.get("question", "")
        queries = state.get("queries", [question])
        
        import asyncio
        from app.nodes.retrieval.search import search_single_query
        
        tasks = [search_single_query(q, top_k=10) for q in queries]
        all_results = await asyncio.gather(*tasks)
        
        seen_contents = set()
        unique_results = []
        for results in all_results:
            for r in results:
                if r.content not in seen_contents:
                    seen_contents.add(r.content)
                    unique_results.append(r)
        
        unique_results = sorted(unique_results, key=lambda x: x.score, reverse=True)
        
        docs = [r.content for r in unique_results]
        scores = [r.score for r in unique_results]
        
        return {
            "docs": docs,
            "scores": scores,
            "confidence": scores[0] if scores else 0.0,
            "best_doc_metadata": unique_results[0].metadata if unique_results else {},
            "vector_results": unique_results[:10]
        }

# For backward compatibility with the existing graph
retrieve_node = RetrievalNode()
retrieve_expanded_node = RetrievalExpandedNode()
