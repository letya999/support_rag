from typing import List
from langfuse import observe
from app.storage.models import SearchResult
from app.nodes.lexical_search.storage import lexical_search_db

@observe(as_type="span")
async def lexical_search_node(query: str, top_k: int = 10) -> List[SearchResult]:
    """
    Execute lexical search (BM25/FTS).
    """
    return await lexical_search_db(query, top_k=top_k)
