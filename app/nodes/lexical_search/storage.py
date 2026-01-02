from typing import List
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def lexical_search_db(query: str, top_k: int = 3) -> List[SearchResult]:
    """
    Search for documents using PostgreSQL full-text search.
    """
    results = []
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Try to use index column fts_en if it exists, otherwise fallback to dynamic
            try:
                await cur.execute(
                    """
                    SELECT content, ts_rank_cd(fts_en, plainto_tsquery('english', %s)) AS score, metadata
                    FROM documents
                    WHERE fts_en @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query, query, top_k)
                )
            except Exception:
                # Fallback to dynamic calculation if column doesn't exist
                await cur.execute(
                    """
                    SELECT content, ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', %s)) AS score, metadata
                    FROM documents
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query, query, top_k)
                )
            rows = await cur.fetchall()
            for row in rows:
                results.append(SearchResult(
                    content=row[0],
                    score=float(row[1]),
                    metadata=row[2]
                ))
    return results
