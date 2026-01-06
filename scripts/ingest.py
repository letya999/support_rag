import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
import asyncio
import psycopg
from qdrant_client.http import models
from app.integrations.embeddings_opensource import get_embeddings_batch
from app.settings import settings
from app.storage.qdrant_client import get_async_qdrant_client

def load_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def ingest_documents(file_path: str):
    """
    Ingest Q&A documents into Postgres and Qdrant.
    """

    if not settings.DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    try:
        data = load_data(file_path)
        print(f"Loaded {len(data)} items from {file_path}")
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # Initialize Qdrant
    qdrant = get_async_qdrant_client()
    collection_name = "documents"
    
    # Recreate collection
    try:
        # Try to delete if exists
        try:
            await qdrant.delete_collection(collection_name)
        except Exception:
            pass # Collection might not exist
            
        await qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )
        print(f"Recreated Qdrant collection: {collection_name}")
    except Exception as e:
        print(f"Error initializing Qdrant: {e}")
        return

    try:
        # Use async connection
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # Ensure table exists
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding vector(384),
                        metadata JSONB
                    );
                """)

                # Add FTS columns and indices if they don't exist
                # English FTS
                try:
                    await cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_en tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;")
                    await cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_fts_en ON documents USING GIN (fts_en);")
                except Exception as e:
                    print(f"Warning: Could not setup English FTS: {e}")

                # Russian FTS
                try:
                    await cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_ru tsvector GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED;")
                    await cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_fts_ru ON documents USING GIN (fts_ru);")
                except Exception as e:
                    print(f"Warning: Could not setup Russian FTS: {e}")

                # Clear existing documents for idempotency
                # RESTART IDENTITY to reset serial ID to 1
                await cur.execute("TRUNCATE TABLE documents RESTART IDENTITY;")
                
                # Ensure correct vector size for Open Source model
                try:
                    await cur.execute("ALTER TABLE documents ALTER COLUMN embedding TYPE vector(384);")
                except Exception as e:
                    print(f"Warning: Could not ensure vector size: {e}")
                
                batch_size = 32
                total_items = len(data)
                
                for i in range(0, total_items, batch_size):
                    batch = data[i:i+batch_size]
                    print(f"Processing batch {i//batch_size + 1}/{(total_items + batch_size - 1)//batch_size}...")
                    
                    batch_contents = []
                    batch_metadatas = []
                    
                    for item in batch:
                        question = item.get('question', '')
                        answer = item.get('answer', '') or item.get('expected_chunk_answer', '')
                        
                        metadata = item.get('metadata', {})
                        # Add standard fields to metadata if they exist in item
                        for field in ['intent', 'category', 'requires_handoff', 'confidence_threshold']:
                            if field in item:
                                metadata[field] = item[field]
                        
                        content = f"Question: {question}\nAnswer: {answer}"
                        batch_contents.append(content)
                        batch_metadatas.append(metadata)
                    
                    # Generate embeddings in batch
                    embeddings = await get_embeddings_batch(batch_contents)
                    
                    points = []
                    
                    for j, (content, embedding, metadata) in enumerate(zip(batch_contents, embeddings, batch_metadatas)):
                        metadata_json = json.dumps(metadata)
                        
                        # Insert into Postgres and get ID
                        await cur.execute(
                            """
                            INSERT INTO documents 
                            (content, embedding, metadata) 
                            VALUES (%s, %s, %s)
                            RETURNING id
                            """,
                            (content, embedding, metadata_json)
                        )
                        row = await cur.fetchone()
                        doc_id = row[0]
                        
                        # Prepare Qdrant point
                        qdrant_payload = {
                            "category": metadata.get("category"),
                            "source": "ingest"
                        }
                        
                        points.append(
                            models.PointStruct(
                                id=doc_id, # Use Postgres ID
                                vector=embedding,
                                payload=qdrant_payload
                            )
                        )
                    
                    # Upsert batch to Qdrant
                    if points:
                        await qdrant.upsert(
                            collection_name=collection_name,
                            points=points
                        )
                
        print(f"Ingestion complete! {len(data)} documents stored in Postgres and Qdrant.")
    except Exception as e:
        print(f"Error during ingestion: {e}")
    finally:
        # Clean up Qdrant client
        # AsyncQdrantClient might need closing if it holds connection, 
        # but the method close() is not always required depending on version. 
        # Recent versions use http client which closes automatically or via context manager.
        # But let's be safe if it has close.
        if hasattr(qdrant, 'close'):
            await qdrant.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Q&A data into the vector store.")
    parser.add_argument(
        "file", 
        type=str, 
        nargs='?',
        default="datasets/qa_data.json",
        help="Path to the JSON file containing Q&A data"
    )
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(ingest_documents(args.file))
