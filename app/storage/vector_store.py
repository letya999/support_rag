from typing import List
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def search_documents(query_embedding: List[float], top_k: int = 3) -> List[SearchResult]:
    """
    Search for documents using vector similarity.
    """
    results = []
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
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
