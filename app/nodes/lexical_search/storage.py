from typing import List
import re
import time
from langfuse import observe
from app.storage.connection import get_db_connection
from app.storage.models import SearchResult

@observe(as_type="span")
async def lexical_search_db(query: str, top_k: int = 3) -> List[SearchResult]:
    """
    Search for documents using PostgreSQL full-text search (Multi-language).
    Translates query if necessary to match document languages.
    """
    from app.nodes.lexical_search.translator import translator
    
    # Prepare queries for each language index
    # If it's RU, we need an EN version for fts_en
    # If it's RU, we need an EN version for fts_en
    # If it's EN, we need a RU version for fts_ru
    try:
        t_start_trans = time.perf_counter()
        query_lang = translator.detect_language(query)
        
        query_en = query
        query_ru = query
        
        if query_lang == "ru":
            query_en = translator.translate_ru_to_en(query)
        elif query_lang == "en":
            query_ru = translator.translate_en_to_ru(query)
        print(f"🔄 Translation took {time.perf_counter() - t_start_trans:.4f}s")
    except Exception as e:
        print(f"⚠️ Query translation failed: {e}")
        query_en = query
        query_ru = query

    
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

    en_tsquery_str = clean_query_for_tsquery(query_en)
    ru_tsquery_str = clean_query_for_tsquery(query_ru)
    
    # Fallback if empty
    if not en_tsquery_str: en_tsquery_str = "EMPTY_QUERY"
    if not ru_tsquery_str: ru_tsquery_str = "EMPTY_QUERY"

    results = []
    
    t_start_db = time.perf_counter()
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            try:
                # Optimized query using search_vector (GIN indexed)
                # We combine English and Russian queries with OR (||)
                await cur.execute(
                    """
                    SELECT 
                        content, 
                        ts_rank_cd(search_vector, query) AS score, 
                        metadata
                    FROM documents, 
                         (SELECT (to_tsquery('english', %s) || to_tsquery('russian', %s)) AS query) AS q
                    WHERE search_vector @@ query
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (en_tsquery_str, ru_tsquery_str, top_k)
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
