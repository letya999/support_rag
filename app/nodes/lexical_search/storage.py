from typing import List
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def lexical_search_db(query: str, top_k: int = 3) -> List[SearchResult]:
    """
    Search for documents using PostgreSQL full-text search (Multi-language).
    Checks both English and Russian indices.
    """
    results = []
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # We search in both fts_en and fts_ru and take the best rank
            try:
                await cur.execute(
                    """
                    SELECT 
                        content, 
                        GREATEST(
                            ts_rank_cd(fts_en, plainto_tsquery('english', %s)),
                            ts_rank_cd(fts_ru, plainto_tsquery('russian', %s))
                        ) AS score, 
                        metadata
                    FROM documents
                    WHERE 
                        fts_en @@ plainto_tsquery('english', %s) OR
                        fts_ru @@ plainto_tsquery('russian', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query, query, query, query, top_k)
                )
                rows = await cur.fetchall()
            except Exception as e:
                print(f"FTS optimized search failed, falling back: {e}")
                # Fallback to dynamic calculation if columns are missing
                await cur.execute(
                    """
                    SELECT 
                        content, 
                        GREATEST(
                            ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', %s)),
                            ts_rank_cd(to_tsvector('russian', content), plainto_tsquery('russian', %s))
                        ) AS score, 
                        metadata
                    FROM documents
                    WHERE 
                        to_tsvector('english', content) @@ plainto_tsquery('english', %s) OR
                        to_tsvector('russian', content) @@ plainto_tsquery('russian', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query, query, query, query, top_k)
                )
                rows = await cur.fetchall()

            for row in rows:
                results.append(SearchResult(
                    content=row[0],
                    score=float(row[1]),
                    metadata=row[2]
                ))
    return results
