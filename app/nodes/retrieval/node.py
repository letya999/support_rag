from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
from app.nodes.retrieval.search import retrieve_context, retrieve_context_expanded
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
        Execute simple vector search retrieval.

        Args:
            state: Current pipeline state

        Returns:
            Dict: State updates with docs and confidence
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
        Execute multi-query expanded retrieval in parallel.

        Args:
            state: Current pipeline state

        Returns:
            Dict: State updates with merged unique documents
        """
        question = state.get("aggregated_query") or state.get("question", "")
        queries = state.get("queries", [question])
        
        # Use centralized logic from search.py (which includes optimizations)
        # Note: retrieve_context_expanded handles expansion internally if we pass 'use_expansion=True',
        # but here the state might already have 'queries' from a separate expansion node?
        # The docstring says "Retrieves documents using multiple expanded queries".
        # If 'queries' are passed, we shouldn't ask valid_context_expanded to expand again if it duplicates work.
        # But retrieve_context_expanded has 'queries = await expander.expand(question)' logic.
        # It doesn't accept 'queries' as argument.
        
        # If we want to use the 'queries' from state:
        # retrieve_context_expanded doesn't support passing pre-calculated queries.
        # We might need to adjust retrieve_context_expanded or just keep using custom logic here 
        # BUT with improved deduplication.
        
        # Since I cannot easily change search.py signature without checking all call sites (though I can search),
        # And RetrievalExpandedNode seems to rely on queries being present or not.
        
        # Actually, let's look at RetrievalExpandedNode logic:
        # queries = state.get("queries", [question])
        # tasks = [search_single_query(q) for q in queries]
        
        # If I want to fix "Multiple iterations", I should optimize THIS block.
        
        import asyncio
        from app.nodes.retrieval.search import search_single_query
        
        tasks = [search_single_query(q, top_k=10) for q in queries]
        all_results = await asyncio.gather(*tasks)
        
        # Optimized deduplication (Max Score Win)
        unique_map = {}
        for results in all_results:
            for r in results:
                if r.content in unique_map:
                    if r.score > unique_map[r.content].score:
                        unique_map[r.content] = r
                else:
                    unique_map[r.content] = r
        
        unique_results = list(unique_map.values())
        unique_results.sort(key=lambda x: x.score, reverse=True)
        
        # Zip for single pass extraction
        docs = []
        scores = []
        if unique_results:
            docs, scores = zip(*[(r.content, r.score) for r in unique_results])
            docs = list(docs)
            scores = list(scores)
        
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
