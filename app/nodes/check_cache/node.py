"""
Check Cache Node: Exact match cache lookup.

Checks Redis cache for exact/normalized query matches.
Does NOT perform semantic similarity search.
"""

from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.services.cache.manager import get_cache_manager
from app.services.cache.query_normalizer import get_normalizer
from app.observability.tracing import observe


class CheckCacheNode(BaseNode):
    """
    Check if query exists in cache (Exact Match only).
    
    Contracts:
        Input:
            Required:
                - question (str): User's question
            Optional: None
        
        Output:
            Guaranteed:
                - cache_hit (bool): Whether cache hit occurred
                - cache_key (str): Normalized cache key used
            Conditional (when cache_hit=True):
                - answer (str): Cached answer
                - confidence (float): Confidence score
                - docs (List[str]): Document IDs
                - cache_reason (str): Reason for hit
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": []
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["cache_hit", "cache_key"],
        "conditional": ["answer", "confidence", "docs", "cache_reason"]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs exact match cache lookup.
        
        Flow:
        1. Normalize query using query normalizer
        2. Check Redis for exact match
        3. Return cached result if found
        """
        question = state.get("question", "")
        
        if not question:
            return {
                "cache_hit": False,
                "cache_key": None
            }
        
        try:
            # Initialize components
            normalizer = get_normalizer()
            cache = await get_cache_manager()
            
            # Step 1: Normalize query for Redis key
            cache_key = normalizer.normalize(question)
            
            # Step 2: Exact Match Check (Redis)
            cached_entry = await cache.get(cache_key)
            
            if cached_entry:
                print(f"✅ Exact Cache HIT for: '{question}'")
                return {
                    "cache_hit": True,
                    "cache_key": cache_key,
                    "answer": cached_entry.answer,
                    "confidence": 1.0,  # Exact match is high confidence
                    "docs": cached_entry.doc_ids,
                    "cache_reason": "exact_match"
                }
            
            # Cache MISS
            print(f"❌ Cache MISS for: '{question}'")
            return {
                "cache_hit": False,
                "cache_key": cache_key
            }
            
        except Exception as e:
            print(f"⚠️  Cache check error: {e}")
            return {
                "cache_hit": False,
                "cache_key": None
            }


# For backward compatibility and LangGraph integration
check_cache_node = CheckCacheNode()
