"""
Cache Similarity Node: Semantic similarity search in cache.

Performs semantic search in Qdrant cache using embeddings.
This is an OPTIONAL node that can be enabled/disabled via config.

Key features:
- Translation-based comparison (uses English translations for better accuracy)
- Document relevance validation
- Configurable similarity threshold
"""

from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.services.cache.similarity import check_semantic_similarity
from app.services.config_loader.loader import get_node_config
from app.observability.tracing import observe


def _validate_doc_relevance(question: str, docs: list, threshold: float = 0.3) -> bool:
    """
    Validate that cached documents are relevant to the question.
    Returns True if documents seem relevant, False otherwise.
    
    Strategy:
    - Extract keywords from question
    - Check if keywords appear in cached documents
    - Return False if no overlap found
    """
    if not docs:
        return False
    
    # Simple keyword extraction (lowercase, remove common words)
    stop_words = {"как", "что", "где", "когда", "почему", "какие", "какой", 
                  "есть", "в", "на", "для", "с", "и", "или", "a", "the", 
                  "is", "are", "in", "on", "for", "with", "and", "or", "what", 
                  "where", "when", "how", "why", "which"}
    
    # Extract question keywords (words longer than 3 chars)
    question_words = set(
        word.lower() for word in question.split()
        if len(word) > 3 and word.lower() not in stop_words
    )
    
    if not question_words:
        return True  # If no keywords extracted, don't filter
    
    # Check if any keyword appears in any document
    docs_text = " ".join(str(doc).lower() for doc in docs)
    
    matches = sum(1 for word in question_words if word in docs_text)
    relevance_ratio = matches / len(question_words)
    
    # Require minimum keyword overlap based on threshold
    is_relevant = relevance_ratio >= threshold
    
    print(f"📊 Doc relevance check: {matches}/{len(question_words)} keywords matched ({relevance_ratio:.2%})")
    return is_relevant


class CacheSimilarityNode(BaseNode):
    """
    Check semantic similarity against cached queries.
    
    Contracts:
        Input:
            Required:
                - question (str): User's question
            Optional:
                - translated_query (str): English translation
                - cache_hit (bool): Skip if already hit (exact match)
        
        Output:
            Guaranteed:
                - cache_hit (bool): Whether semantic cache hit occurred
            Conditional (when cache_hit=True):
                - answer (str): Cached answer
                - confidence (float): Similarity score
                - docs (List[str]): Document IDs
                - cache_reason (str): Reason for hit
    
    Note: This node only executes if cache_hit is False (skip if exact match found).
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": ["translated_query", "cache_hit"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["cache_hit"],
        "conditional": ["answer", "confidence", "docs", "cache_reason"]
    }
    
    def __init__(self):
        super().__init__("cache_similarity")
        # Load node-specific config
        node_cfg = get_node_config("cache_similarity")
        params = node_cfg.get("parameters", {})
        
        # similarity_threshold comes from shared config (cache.yaml -> semantic.threshold)
        # via services/cache/similarity.get_similarity_threshold()
        from app.services.cache.similarity import get_similarity_threshold
        self.similarity_threshold = get_similarity_threshold()
        
        # Node-specific parameters
        self.use_translation = params.get("use_english_translation", True)
        self.validate_relevance = params.get("validate_doc_relevance", True)
        self.relevance_threshold = params.get("relevance_threshold", 0.3)
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs semantic similarity search in cache.
        
        Flow:
        1. Skip if exact match already found
        2. Use translated query if available and configured
        3. Search Qdrant for similar cached queries
        4. Validate document relevance
        5. Return cache hit if similarity above threshold
        """
        # Skip if exact match already found
        if state.get("cache_hit", False):
            return {}
        
        question = state.get("question", "")
        if not question:
            return {"cache_hit": False}
        
        try:
            # Get translated query if available
            translated_query = state.get("translated_query")
            
            # Perform semantic similarity search
            result = await check_semantic_similarity(
                question=question,
                translated_query=translated_query,
                similarity_threshold=self.similarity_threshold,
                use_translation=self.use_translation
            )
            
            if result:
                # Validate document relevance if enabled
                if self.validate_relevance:
                    docs = result.get("doc_ids", [])
                    if not _validate_doc_relevance(question, docs, self.relevance_threshold):
                        print(f"⚠️  Cache hit rejected: docs not relevant to query")
                        print(f"   Score: {result['score']:.4f} >= {self.similarity_threshold}, but docs failed validation")
                        return {"cache_hit": False}
                
                # Cache hit!
                score = result["score"]
                print(f"✅ Semantic Cache HIT for: '{question}'")
                print(f"   Score: {score:.4f} >= {self.similarity_threshold}, docs validated" if self.validate_relevance else "")
                
                return {
                    "cache_hit": True,
                    "answer": result["answer"],
                    "confidence": score,
                    "docs": result["doc_ids"],
                    "cache_reason": f"semantic_match ({score:.2f})"
                }
            
            # No match found
            return {"cache_hit": False}
            
        except Exception as e:
            print(f"⚠️  Cache similarity error: {e}")
            return {"cache_hit": False}


# For backward compatibility and LangGraph integration
cache_similarity_node = CacheSimilarityNode()
