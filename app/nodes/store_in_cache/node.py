"""
Store in Cache Node: Store generated answers in cache.

Stores successful answers in both Redis (exact match) 
and optionally in Qdrant (semantic search).
"""

from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.services.cache.manager import get_cache_manager
from app.services.cache.similarity import store_in_semantic_cache
from app.services.cache.models import CacheEntry
from app.services.config_loader.loader import get_node_config
from app.observability.tracing import observe
from app.integrations.embeddings import get_embedding


class StoreInCacheNode(BaseNode):
    """
    Store the generated answer in cache (Redis + optionally Qdrant).
    
    Contracts:
        Input:
            Required:
                - question (str): Original question
                - answer (str): Generated answer
                - cache_key (str): Normalized cache key
            Optional:
                - confidence (float): Answer confidence score
                - docs (List[str]): Document IDs used
                - translated_query (str): Translated query
                - question_embedding (List[float]): Pre-computed embedding
                - cache_hit (bool): Skip if already cached
        
        Output:
            Guaranteed: None (side effects only)
            Conditional:
                - cached (bool): Whether caching succeeded
    
    State Impact:
        - No state fields are modified
        - Side effect: stores data in Redis and Qdrant
    """
    
    INPUT_CONTRACT = {
        "required": ["question", "answer", "cache_key"],
        "optional": [
            "confidence", 
            "docs", 
            "translated_query", 
            "question_embedding",
            "cache_hit"
        ]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": [],
        "conditional": ["cached"]
    }
    
    def __init__(self):
        super().__init__()
        # Load configurations
        node_cfg = get_node_config("store_in_cache")
        
        # min_confidence_to_cache comes from shared config (cache.yaml -> semantic.min_confidence_to_cache)
        from app.services.config_loader.loader import load_shared_config
        cache_cfg = load_shared_config("cache")
        semantic_cfg = cache_cfg.get("parameters", {}).get("semantic", {})
        self.min_confidence = semantic_cfg.get("min_confidence_to_cache", 0.7)
        
        # Node-specific parameter
        self.store_semantic = node_cfg.get("parameters", {}).get("store_in_semantic", True)
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stores answer in cache if conditions are met.
        
        Flow:
        1. Check if this was a cache miss (don't re-cache cache hits)
        2. Validate confidence meets threshold
        3. Store in Redis (exact match)
        4. Optionally store in Qdrant (semantic search)
        """
        try:
            # Only store if this was a cache miss
            if state.get("cache_hit", False):
                return {}
            
            # Extract required fields
            answer = state.get("answer")
            cache_key = state.get("cache_key")
            question = state.get("question")
            
            if not answer or not cache_key or not question:
                return {}
            
            # Get optional fields
            confidence = state.get("confidence", 0.7)
            docs = state.get("docs", [])
            doc_ids = [d for d in docs if isinstance(d, str)] if docs else []
            
            # Check confidence threshold
            if confidence < self.min_confidence:
                print(f"⚠️  Skipping cache: confidence {confidence:.2f} < {self.min_confidence}")
                return {}
            
            # Initialize cache manager
            cache = await get_cache_manager()
            
            # 1. Store in Redis (Exact match)
            cache_entry = CacheEntry(
                query_normalized=cache_key,
                query_original=question,
                answer=answer,
                doc_ids=doc_ids,
                confidence=confidence,
                hit_count=0
            )
            await cache.set(cache_key, cache_entry)
            print(f"💾 Cached answer for: '{question}'")
            
            # 2. Optionally store in Qdrant (Semantic match)
            if self.store_semantic:
                # Try to get embedding from state (may have been computed earlier)
                embedding = state.get("question_embedding")
                
                # If not in state, compute it now
                if not embedding:
                    embedding = await get_embedding(question, is_query=True)
                
                if embedding:
                    # Prepare metadata
                    metadata = {}
                    translated_query = state.get("translated_query")
                    if translated_query:
                        metadata["translated_query"] = translated_query
                    
                    # Store in semantic cache
                    await store_in_semantic_cache(
                        question=question,
                        answer=answer,
                        doc_ids=doc_ids,
                        embedding=embedding,
                        metadata=metadata
                    )
                else:
                    print("⚠️  Missing embedding, skipping semantic cache storage.")
            
            return {}
            
        except Exception as e:
            print(f"⚠️  Cache store error: {e}")
            return {}


# For backward compatibility and LangGraph integration
store_in_cache_node = StoreInCacheNode()
