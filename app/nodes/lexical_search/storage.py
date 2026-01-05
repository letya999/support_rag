from typing import List
import re
import time
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def lexical_search_db(
    query: str, 
    top_k: int = 3,
    detected_language: str = None,
    document_language: str = "ru"
) -> List[SearchResult]:
    """
    Search for documents using PostgreSQL full-text search.
    
    Note: Query should already be translated to document_language 
    by query_translation node before reaching this function.
    
    Args:
        query: User's search query (already translated)
        top_k: Number of results to return
        detected_language: Language detected by language_detection node (optional, for logging)
        document_language: Primary language of documents in the database (default: 'ru')
    """
    from app.services.config_loader.loader import get_global_param
    
    # Get document language from config if not provided
    if document_language == "ru":
        document_language = get_global_param("default_language", "ru")
    
    print(f"🔍 Lexical search for: '{query}' (document_language={document_language})")
    
    # Helper to construct OR-based tsquery string
    def clean_query_for_tsquery(text: str) -> str:
        # Remove special characters that interfere with tsquery syntax
        # Keep alphanumeric and spaces
        cleaned = re.sub(r'[^\w\s]', '', text)
        words = cleaned.split()
        if not words:
            return ""
        # Join with | for OR logic
        return " | ".join(words)

    # Determine which tsquery config to use based on document language
    if document_language == "ru":
        tsquery_config = "russian"
    else:
        tsquery_config = "english"
    
    tsquery_str = clean_query_for_tsquery(query)
    
    # Fallback if empty
    if not tsquery_str: 
        tsquery_str = "EMPTY_QUERY"

    results = []
    
    t_start_db = time.perf_counter()
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            try:
                # Optimized query using search_vector (GIN indexed)
                await cur.execute(
                    """
                    SELECT 
                        content, 
                        ts_rank_cd(search_vector, query) AS score, 
                        metadata
                    FROM documents, 
                         (SELECT to_tsquery(%s, %s) AS query) AS q
                    WHERE search_vector @@ query
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (tsquery_config, tsquery_str, top_k)
                )
                rows = await cur.fetchall()
            except Exception as e:
                print(f"Index scan failed, falling back: {e}")
                # Fallback to simple query if something goes wrong
                await cur.execute(
                    """
                    SELECT content, 0.0, metadata
                    FROM documents
                    WHERE content ILIKE %s
                    LIMIT %s
                    """,
                    (f"%{query}%", top_k)
                )
                rows = await cur.fetchall()

            for row in rows:
                results.append(SearchResult(
                    content=row[0],
                    score=float(row[1]),
                    metadata=row[2]
                ))
    print(f"🐘 DB Search took {time.perf_counter() - t_start_db:.4f}s")
    return results
