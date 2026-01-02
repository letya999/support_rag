from typing import List, Optional
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def search_documents(
    query_embedding: List[float],
    top_k: int = 3,
    category_filter: Optional[str] = None
) -> List[SearchResult]:
    """
    Search for documents using vector similarity with optional category filtering.

    Args:
        query_embedding: Vector embedding of the query
        top_k: Number of results to return
        category_filter: Optional category to filter documents by
    """
    results = []

    # Build base query
    query = """
    SELECT content, 1 - (embedding <=> %s::vector) AS score, metadata
    FROM documents
    """
    params = [query_embedding]

    # Add category filter if provided
    if category_filter:
        query += "WHERE metadata->>'category' = %s"
        params.append(category_filter)

    query += "ORDER BY score DESC LIMIT %s;"
    params.append(top_k)

    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
            for row in rows:
                results.append(SearchResult(
                    content=row[0],
                    score=float(row[1]),
                    metadata=row[2]
                ))
    return results
