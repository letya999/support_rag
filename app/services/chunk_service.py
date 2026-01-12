
import logging
from typing import List, Dict, Any, Optional
import json
import psycopg
from app.settings import settings
from app.storage.qdrant_client import get_async_qdrant_client
from qdrant_client.http import models

logger = logging.getLogger(__name__)

class ChunkService:
    async def get_chunk(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")
            
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, content, embedding, metadata FROM documents WHERE id = %s",
                    (chunk_id,)
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "content": row[1],
                        "embedding": row[2], # Vector string or list
                        "metadata": row[3] or {}
                    }
        return None

    async def list_chunks(
        self,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        chunk_id: Optional[int] = None,
        intent: Optional[str] = None,
        category: Optional[str] = None,
        source_document: Optional[str] = None,
        requires_handoff: Optional[bool] = None,
        extraction_date: Optional[str] = None
    ) -> Dict[str, Any]:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")
            
        offset = (page - 1) * page_size
        
        query = "SELECT id, content, metadata FROM documents WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM documents WHERE 1=1"
        params = []
        
        if chunk_id is not None:
            query += " AND id = %s"
            count_query += " AND id = %s"
            params.append(chunk_id)
            
        if search:
            # Simple content ILIKE
            query += " AND content ILIKE %s"
            count_query += " AND content ILIKE %s"
            params.append(f"%{search}%")
            
        if intent:
            query += " AND metadata->>'intent' = %s"
            count_query += " AND metadata->>'intent' = %s"
            params.append(intent)
            
        if category:
            query += " AND metadata->>'category' = %s"
            count_query += " AND metadata->>'category' = %s"
            params.append(category)

        if source_document:
            query += " AND metadata->>'source_document' = %s"
            count_query += " AND metadata->>'source_document' = %s"
            params.append(source_document)

        if extraction_date:
             query += " AND metadata->>'extraction_date' = %s"
             count_query += " AND metadata->>'extraction_date' = %s"
             params.append(extraction_date)

        if requires_handoff is not None:
            # requires_handoff in metadata is typically boolean true/false
            # We cast to text 'true'/'false' to safely compare if stored as JSON boolean
            if requires_handoff:
                query += " AND (metadata->'requires_handoff')::boolean IS TRUE"
                count_query += " AND (metadata->'requires_handoff')::boolean IS TRUE"
            else:
                # Handle both false and null (if implies false)? 
                # Request said: "requires_handoff": false exists. 
                # Let's assume strict check for now.
                query += " AND ((metadata->'requires_handoff')::boolean IS FALSE OR metadata->'requires_handoff' IS NULL)"
                count_query += " AND ((metadata->'requires_handoff')::boolean IS FALSE OR metadata->'requires_handoff' IS NULL)"

        # Order and Limit
        query += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params_with_paging = params + [page_size, offset]
        
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # Get Count
                await cur.execute(count_query, params)
                total_count = (await cur.fetchone())[0]
                
                # Get Data
                await cur.execute(query, params_with_paging)
                rows = await cur.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "content": row[1],
                        "metadata": row[2] or {}
                    })
                    
        return {
            "items": results,
            "total": total_count,
            "page": page,
            "size": page_size
        }

    async def update_chunk(self, chunk_id: int, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        # This mirrors staging update_chunk but commits to DB
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")
            
        # Get current first to merge metadata if needed, usually we just merge passed metadata
        
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # 1. Update DB
                if content and metadata:
                    await cur.execute(
                        "UPDATE documents SET content = %s, metadata = metadata || %s::jsonb WHERE id = %s RETURNING id, content, metadata",
                        (content, json.dumps(metadata), chunk_id)
                    )
                elif content:
                    await cur.execute(
                        "UPDATE documents SET content = %s WHERE id = %s RETURNING id, content, metadata",
                        (content, chunk_id)
                    )
                elif metadata:
                    await cur.execute(
                        "UPDATE documents SET metadata = metadata || %s::jsonb WHERE id = %s RETURNING id, content, metadata",
                        (json.dumps(metadata), chunk_id)
                    )
                else:
                    return None # No op

                row = await cur.fetchone()
                if not row:
                    return None
                
                updated_chunk = {
                    "id": row[0],
                    "content": row[1],
                    "metadata": row[2]
                }

                # 2. Update Qdrant (Payload only for now, unless we want to re-embed)
                # If content changed, strictly we should re-embed. 
                # For now, we will update Payload.
                if metadata:
                    try:
                        qdrant = get_async_qdrant_client()
                        await qdrant.set_payload(
                            collection_name="documents",
                            payload=metadata,
                            points=[chunk_id]
                        )
                    except Exception as e:
                        logger.error(f"Failed to update Qdrant payload for chunk {chunk_id}: {e}")

                return updated_chunk
                
    async def delete_chunk(self, chunk_id: int) -> bool:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")

        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM documents WHERE id = %s", (chunk_id,))
                
                if cur.rowcount > 0:
                    # Delete from Qdrant
                    try:
                        qdrant = get_async_qdrant_client()
                        await qdrant.delete(
                            collection_name="documents",
                            points_selector=models.PointIdsList(points=[chunk_id])
                        )
                    except Exception as e:
                        logger.error(f"Failed to delete from Qdrant chunk {chunk_id}: {e}")
                    return True
        return False

chunk_service = ChunkService()
