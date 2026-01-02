import os
import psycopg
from typing import List, Dict, Any
from langfuse import observe
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

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
                SELECT content, 1 - (embedding <=> %s::vector) AS score, metadata
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
                    "score": float(row[1]),
                    "metadata": row[2]
                })
    return results
