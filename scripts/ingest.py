import os
import json
import argparse
import asyncio
import psycopg
from app.integrations.embeddings import get_embedding
from app.config.settings import settings

def load_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def ingest_documents(file_path: str):
    """
    Ingest Q&A documents into the vector store.
    """
    if not settings.OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY is not set.")
        return
    if not settings.DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    try:
        data = load_data(file_path)
        print(f"Loaded {len(data)} items from {file_path}")
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    try:
        # Use async connection
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # Clear existing documents for idempotency
                await cur.execute("TRUNCATE TABLE documents;")
                
                for item in data:
                    question = item.get('question', '')
                    answer = item.get('answer', '') or item.get('expected_chunk_answer', '')
                    
                    metadata = item.get('metadata', {})
                    # Add standard fields to metadata if they exist in item
                    for field in ['intent', 'category', 'requires_handoff', 'confidence_threshold']:
                        if field in item:
                            metadata[field] = item[field]
                    
                    metadata_json = json.dumps(metadata)

                    content = f"Question: {question}\nAnswer: {answer}"
                    
                    print(f"Generating embedding for: {question[:50]}...")
                    embedding = await get_embedding(content)
                    
                    await cur.execute(
                        """
                        INSERT INTO documents 
                        (content, embedding, metadata) 
                        VALUES (%s, %s, %s)
                        """,
                        (content, embedding, metadata_json)
                    )
                
        print(f"Ingestion complete! {len(data)} documents stored in the database.")
    except Exception as e:
        print(f"Error during ingestion: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Q&A data into the vector store.")
    parser.add_argument(
        "--file", 
        type=str, 
        default="datasets/qa_data.json",
        help="Path to the JSON file containing Q&A data"
    )
    args = parser.parse_args()
    
    asyncio.run(ingest_documents(args.file))
