from typing import List, Optional, Union
from qdrant_client.http import models
from app.storage.connection import get_db_connection
from app.storage.qdrant_client import get_async_qdrant_client
from app.storage.models import SearchResult
from app.observability.tracing import observe, langfuse_context

@observe(as_type="span")
async def vector_search(
    query_embedding: List[float], 
    top_k: int = 3, 
    category_filter: Optional[Union[str, List[str]]] = None
) -> List[SearchResult]:
    """
    Search for documents using Qdrant vector search, then fetch content from Postgres.
    
    Contracts:
        Input:
            Required: query_embedding (List[float])
            Optional: top_k (int), category_filter (str/List[str])
        Output:
            Guaranteed: List[SearchResult]
    """
    # Log inputs explicitly (not the full embedding)
    if langfuse_context:
        langfuse_context.update_current_observation(
            input={"embedding_dim": len(query_embedding), "top_k": top_k, "category_filter": category_filter}
        )
    
    client = get_async_qdrant_client()
    
    # Construct filter
    query_filter = None
    if category_filter:
        if isinstance(category_filter, list):
            match_condition = models.MatchAny(any=category_filter)
        else:
            match_condition = models.MatchValue(value=category_filter)

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="category",
                    match=match_condition
                )
            ]
        )

    # Search Qdrant
    try:
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
        
        # Reset client on connection errors to force reconnection next time
        if "Channel is closed" in str(e) or "Connection refused" in str(e):
             from app.storage.qdrant_client import reset_async_qdrant_client
             reset_async_qdrant_client()
             print("🔄 Qdrant client reset due to connection error.")

        if langfuse_context:
            langfuse_context.update_current_observation(output={"error": str(e), "results_count": 0})
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
    
    # Log output explicitly
    if langfuse_context:
        langfuse_context.update_current_observation(
            output={
                "results_count": len(results),
                "top_score": results[0].score if results else 0.0
            }
        )
    
    return results
