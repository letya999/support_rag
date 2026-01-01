import os
import json
import psycopg
import argparse
import asyncio
from dotenv import load_dotenv

load_dotenv()

from app.utils import get_embedding, DATABASE_URL, OPENAI_API_KEY

def load_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def ingest(file_path):
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY is not set.")
        return
    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set.")
        return

    try:
        data = load_data(file_path)
        print(f"Loaded {len(data)} items from {file_path}")
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Clear existing documents for idempotency
                cur.execute("TRUNCATE TABLE documents;")
                
                for item in data:
                    question = item.get('question', '')
                    answer = item.get('answer', '')
                    
                    # Combine Q&A into one chunk as per requirements
                    content = f"Question: {question}\nAnswer: {answer}"
                    
                    print(f"Generating embedding for: {question[:50]}...")
                    # Now get_embedding is async
                    embedding = await get_embedding(content)
                    
                    cur.execute(
                        "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
                        (content, embedding)
                    )
                
                conn.commit()
        print(f"Ingestion complete! {len(data)} documents stored in the database.")
    except Exception as e:
        print(f"Error during ingestion: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Q&A data into the vector store.")
    parser.add_argument(
        "--file", 
        type=str, 
        default="qa_data.json",
        help="Path to the JSON file containing Q&A data (default: qa_data.json)"
    )
    args = parser.parse_args()
    
    asyncio.run(ingest(args.file))
