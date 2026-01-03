import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import psycopg
import ast
from qdrant_client.http import models
from app.config.settings import settings
from app.storage.qdrant_client import get_async_qdrant_client

async def migrate():
    print("Starting migration from Postgres to Qdrant...")
    
    if not settings.DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    # 1. Fetch data from Postgres
    documents = []
    try:
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                print("Fetching documents from Postgres...")
                await cur.execute("SELECT id, embedding, metadata FROM documents WHERE embedding IS NOT NULL")
                rows = await cur.fetchall()
                print(f"Found {len(rows)} documents.")
                
                for row in rows:
                    doc_id = row[0]
                    embedding_val = row[1]
                    metadata = row[2] or {}
                    
                    vector = []
                    if isinstance(embedding_val, str):
                        # Parse vector string "[0.1, 0.2, ...]"
                        try:
                            vector = json.loads(embedding_val)
                        except json.JSONDecodeError:
                            # Fallback if json fails (unlikely for vector output)
                            # Maybe it's not valid JSON? Postgres vector output is [ ... ]
                            vector = ast.literal_eval(embedding_val)
                    elif isinstance(embedding_val, list):
                        vector = embedding_val
                    else:
                        # numpy array or other
                        vector = list(embedding_val)
                    
                    documents.append({
                        "id": doc_id,
                        "vector": vector,
                        "payload": {
                            "category": metadata.get("category"),
                            "source": "migration"
                        }
                    })
    except Exception as e:
        print(f"Postgres error: {e}")
        return

    if not documents:
        print("No documents to migrate.")
        return

    # 2. Push to Qdrant
    qdrant = get_async_qdrant_client()
    collection_name = "documents"
    
    try:
        # Check if Qdrant is up
        try:
            await qdrant.get_collections()
        except Exception:
            print("Qdrant not ready, waiting 5s...")
            await asyncio.sleep(5)
        
        # Ensure collection exists
        # We don't delete here to avoid losing data if script is run twice, 
        # but we need to ensure it exists.
        collections = await qdrant.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)
        
        if not exists:
            print(f"Creating collection {collection_name}...")
            await qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )
        
        # Upsert
        points = [
            models.PointStruct(
                id=doc["id"],
                vector=doc["vector"],
                payload=doc["payload"]
            ) 
            for doc in documents
        ]
        
        batch_size = 50
        total = len(points)
        print(f"Upserting {total} points to Qdrant...")
        
        for i in range(0, total, batch_size):
            batch = points[i:i+batch_size]
            await qdrant.upsert(
                collection_name=collection_name,
                points=batch
            )
            print(f"Processed {min(i+batch_size, total)}/{total}")
            
        print("Migration complete!")
        
    except Exception as e:
        print(f"Qdrant error: {e}")
    finally:
        if hasattr(qdrant, 'close'):
            await qdrant.close()

if __name__ == "__main__":
    asyncio.run(migrate())
