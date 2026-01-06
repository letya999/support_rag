import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import psycopg
from qdrant_client import AsyncQdrantClient
from app.settings import settings

async def reset_db():
    print("Resetting Databases...")
    
    # 1. Reset Postgres
    if settings.DATABASE_URL:
        try:
            async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
                async with conn.cursor() as cur:
                    print("Dropping table 'documents' in Postgres...")
                    await cur.execute("DROP TABLE IF EXISTS documents CASCADE;")
                    print("Postgres cleanup done.")
        except Exception as e:
            print(f"Error resetting Postgres: {e}")
    else:
        print("DATABASE_URL not set, skipping Postgres.")

    # 2. Reset Qdrant
    if settings.QDRANT_URL:
        try:
            client = AsyncQdrantClient(url=settings.QDRANT_URL)
            collections = await client.get_collections()
            for col in collections.collections:
                print(f"Deleting Qdrant collection: {col.name}...")
                await client.delete_collection(col.name)
            print("Qdrant cleanup done.")
            await client.close()
        except Exception as e:
            print(f"Error resetting Qdrant: {e}")
    else:
        print("QDRANT_URL not set, skipping Qdrant.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_db())
