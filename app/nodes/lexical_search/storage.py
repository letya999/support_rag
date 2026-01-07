from typing import List, Optional
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
    document_language: str = "ru",
    category_filter: Optional[str] = None
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
        category_filter: Optional category to filter by (from config, not hardcoded)
    """
    from app.services.config_loader.loader import get_global_param
    
    # Get document language from config if not provided
    if document_language == "ru":
        document_language = get_global_param("default_language", "ru")
    
    filter_info = f", category_filter={category_filter}" if category_filter else ""
    print(f"🔍 Lexical search for: '{query}' (document_language={document_language}{filter_info})")
    
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

    # Determine which tsquery config to use based on document language or query content
    # Simple heuristic: if query contains latin characters, it's likely English (translated or original)
    # This prevents using 'russian' config for english words which breaks stemming
    has_latin = any('a' <= char.lower() <= 'z' for char in query)
    
    if has_latin:
        tsquery_config = "english"
        print(f"🌍 Detected Latin characters in query, forcing tsquery_config='english'")
    elif document_language == "ru":
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
                # Build query dynamically based on whether category_filter is provided
                base_query = """
                    SELECT 
                        content, 
                        ts_rank_cd(search_vector, query) AS score, 
                        metadata
                    FROM documents, 
                         (SELECT to_tsquery(%s, %s) AS query) AS q
                    WHERE search_vector @@ query
                """
                params = [tsquery_config, tsquery_str]
                
                if category_filter:
                    base_query += " AND metadata->>'category' = %s"
                    params.append(category_filter)
                
                base_query += " ORDER BY score DESC LIMIT %s;"
                params.append(top_k)
                
                await cur.execute(base_query, tuple(params))
                rows = await cur.fetchall()
            except Exception as e:
                print(f"Index scan failed, falling back: {e}")
                # Fallback to simple query if something goes wrong
                fallback_query = """
                    SELECT content, 0.0, metadata
                    FROM documents
                    WHERE content ILIKE %s
                """
                params = [f"%{query}%"]
                
                if category_filter:
                    fallback_query += " AND metadata->>'category' = %s"
                    params.append(category_filter)
                
                fallback_query += " LIMIT %s"
                params.append(top_k)
                
                await cur.execute(fallback_query, tuple(params))
                rows = await cur.fetchall()

            for row in rows:
                results.append(SearchResult(
                    content=row[0],
                    score=float(row[1]),
                    metadata=row[2]
                ))
    print(f"🐘 DB Search took {time.perf_counter() - t_start_db:.4f}s")
    return results
