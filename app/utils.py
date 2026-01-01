import os
import psycopg
from langfuse.openai import OpenAI
from typing import List, Dict, Any
from langfuse import observe
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

@observe(as_type="span")
async def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")
    # Use the async client if possible, but Langfuse wrapper is often sync-first
    # For now, keeping the call but making the function async to preserve contextvars
    client = OpenAI(api_key=OPENAI_API_KEY)
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding

@observe(as_type="span")
async def search_documents(query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set.")
    
    results = []
    # Using <=> for cosine distance (1 - cosine similarity)
    # Cosine similarity = 1 - (embedding <=> query_embedding)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, 1 - (embedding <=> %s::vector) AS score
                FROM documents
                ORDER BY score DESC
                LIMIT %s;
                """,
                (query_embedding, top_k)
            )
            rows = cur.fetchall()
            for row in rows:
                results.append({
                    "content": row[0],
                    "score": float(row[1])
                })
    return results
