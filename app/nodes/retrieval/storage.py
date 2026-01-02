from typing import List
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def vector_search(query_embedding: List[float], top_k: int = 3, category_filter: str = None) -> List[SearchResult]:
    """
    Search for documents using vector similarity.
    """
    results = []
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            if category_filter:
                await cur.execute(
                    """
                    SELECT content, 1 - (embedding <=> %s::vector) AS score, metadata
                    FROM documents
                    WHERE metadata->>'category' = %s
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query_embedding, category_filter, top_k)
                )
            else:
                await cur.execute(
                    """
                    SELECT content, 1 - (embedding <=> %s::vector) AS score, metadata
                    FROM documents
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query_embedding, top_k)
                )
            rows = await cur.fetchall()
            for row in rows:
                results.append(SearchResult(
                    content=row[0],
                    score=float(row[1]),
                    metadata=row[2]
                ))
    return results
