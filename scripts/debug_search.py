import asyncio
import os
import sys
import selectors
from dotenv import load_dotenv
load_dotenv()

from app.integrations.embeddings import get_embedding
from app.storage.vector_store import search_documents

async def test_search():
    query = "какие есть способы доставки?"
    print(f"Searching for: {query}")
    emb = await get_embedding(query)
    results = await search_documents(emb, top_k=5)
    for i, r in enumerate(results):
        print(f"{i+1}. Score: {r.score:.4f}")
        print(f"Content: {r.content}")
        print("-" * 20)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_search())
