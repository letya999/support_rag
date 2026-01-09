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

# --- Auto-fix URLs for local execution (outside Docker) ---
def _fix_local_urls():
    # Check if we are running outside Docker
    if not os.path.exists("/.dockerenv"):
        # Update settings object directly as it is already initialized
        if "qdrant:6333" in settings.QDRANT_URL:
            settings.QDRANT_URL = settings.QDRANT_URL.replace("qdrant:6333", "localhost:6333")
            os.environ["QDRANT_URL"] = settings.QDRANT_URL
            
        if "redis:6379" in settings.REDIS_URL:
            settings.REDIS_URL = settings.REDIS_URL.replace("redis:6379", "localhost:6379")
            os.environ["REDIS_URL"] = settings.REDIS_URL

_fix_local_urls()

def load_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def ingest_documents(file_path: str, append: bool = False):
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
    
    # Initialize Qdrant Collection
    try:
        # Check if collection exists
        col_exists = False
        try:
            await qdrant.get_collection(collection_name)
            col_exists = True
        except Exception:
            col_exists = False

        if not append or not col_exists:
            if col_exists and not append:
                try:
                    await qdrant.delete_collection(collection_name)
                except Exception:
                    pass
            
            await qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )
            print(f"{'Recreated' if not append else 'Created'} Qdrant collection: {collection_name}")
        else:
            print(f"Using existing Qdrant collection: {collection_name} (append mode)")
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
                # ... [FTS logic remains same as it uses IF NOT EXISTS] ...
                try:
                    await cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_en tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;")
                    await cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_fts_en ON documents USING GIN (fts_en);")
                except Exception as e:
                    print(f"Warning: Could not setup English FTS: {e}")

                try:
                    await cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_ru tsvector GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED;")
                    await cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_fts_ru ON documents USING GIN (fts_ru);")
                except Exception as e:
                    print(f"Warning: Could not setup Russian FTS: {e}")

                # Handle Clear vs Append
                if not append:
                    print("Clearing existing documents (idempotency)...")
                    await cur.execute("TRUNCATE TABLE documents RESTART IDENTITY;")
                else:
                    print("Appending to existing documents...")
                
                # Ensure correct vector size
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
                        for field in ['intent', 'category', 'requires_handoff', 'confidence_threshold']:
                            if field in item:
                                metadata[field] = item[field]
                        
                        content = f"Question: {question}\nAnswer: {answer}"
                        batch_contents.append(content)
                        batch_metadatas.append(metadata)
                    
                    embeddings = await get_embeddings_batch(batch_contents)
                    points = []
                    
                    for j, (content, embedding, metadata) in enumerate(zip(batch_contents, embeddings, batch_metadatas)):
                        metadata_json = json.dumps(metadata)
                        
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
                        
                        qdrant_payload = {
                            "category": metadata.get("category"),
                            "source": "ingest"
                        }
                        
                        points.append(
                            models.PointStruct(
                                id=doc_id, 
                                vector=embedding,
                                payload=qdrant_payload
                            )
                        )
                    
                    if points:
                        await qdrant.upsert(
                            collection_name=collection_name,
                            points=points
                        )
                
        print(f"Ingestion complete! {len(data)} documents processed.")
    except Exception as e:
        print(f"Error during ingestion: {e}")
    finally:
        if hasattr(qdrant, 'close'):
            await qdrant.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Q&A data into the vector store.")
    parser.add_argument(
        "file", 
        type=str, 
        nargs='?',
        default="datasets/qa_data.json",
        help="Path to the JSON file"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing data instead of clearing"
    )
    parser.add_argument(
        "--qdrant-url",
        type=str,
        help="Override Qdrant URL"
    )
    args = parser.parse_args()
    
    if args.qdrant_url:
        settings.QDRANT_URL = args.qdrant_url
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(ingest_documents(args.file, append=args.append))
