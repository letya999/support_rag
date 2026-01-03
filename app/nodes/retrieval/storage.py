from typing import List, Optional
from langfuse import observe
from qdrant_client.http import models
from app.storage.connection import get_db_connection
from app.storage.qdrant_client import get_async_qdrant_client
from app.storage.models import SearchResult

@observe(as_type="span")
async def vector_search(query_embedding: List[float], top_k: int = 3, category_filter: Optional[str] = None) -> List[SearchResult]:
    """
    Search for documents using Qdrant vector search, then fetch content from Postgres.
    """
    client = get_async_qdrant_client()
    
    # Construct filter
    query_filter = None
    if category_filter:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="category",
                    match=models.MatchValue(value=category_filter)
                )
            ]
        )

    # Search Qdrant
    try:
        # Note: AsyncQdrantClient v1.16+ might not expose 'search' directly or prefers 'query_points'.
        # We use query_points which maps to the new Query API.
        # query: The vector (or Query object)
        # filter: The filter (was query_filter in search)
        
        result = await client.query_points(
            collection_name="documents",
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            with_payload=False # We fetch content from Postgres
        )
        points = result.points
    except Exception as e:
        # Handle cases where Qdrant is not ready or collection missing
        print(f"Qdrant search error: {e}")
        return []

    if not points:
        return []

    # Get IDs
    # Assuming IDs are stored as integers matching Postgres IDs
    ids = [point.id for point in points]

    results = []
    
    # Fetch content from Postgres
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, content, metadata
                FROM documents
                WHERE id = ANY(%s)
                """,
                (ids,)
            )
            rows = await cur.fetchall()
            
            # Create a map for quick lookup
            doc_map = {row[0]: (row[1], row[2]) for row in rows}
            
            # Reconstruct results in the order returned by Qdrant (sorted by score)
            for point in points:
                # Qdrant IDs can be integers
                point_id = point.id
                if point_id in doc_map:
                    content, metadata = doc_map[point_id]
                    results.append(SearchResult(
                        content=content,
                        score=float(point.score),
                        metadata=metadata
                    ))
    
    return results
