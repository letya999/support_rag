import asyncio
import sys
import os

sys.path.append(os.getcwd())
from app.storage.connection import get_db_connection
from app.storage.qdrant_client import get_async_qdrant_client
from qdrant_client.http import models

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def clean_duplicates():
    qdrant = get_async_qdrant_client()
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            print("🧹 Cleaning duplicates...")
            
            # Find duplicates keeping the one with the lowest ID (first inserted)
            query = """
                DELETE FROM documents a USING documents b
                WHERE a.id > b.id AND a.content = b.content
                RETURNING a.id, a.content;
            """
            
            await cur.execute(query)
            deleted_rows = await cur.fetchall()
            
            print(f"Deleted {len(deleted_rows)} duplicate rows from PostgreSQL.")
            
            if deleted_rows:
                deleted_ids = [row[0] for row in deleted_rows]
                print(f"Removing corresponding vectors from Qdrant: {deleted_ids}")
                
                try:
                    # Delete from Qdrant
                    await qdrant.delete(
                        collection_name="documents",
                        points_selector=models.PointIdsList(
                            points=deleted_ids
                        )
                    )
                    print("✅ Qdrant cleanup successful.")
                except Exception as e:
                    print(f"❌ Error cleaning Qdrant: {e}")
            else:
                print("No duplicates found to delete.")

if __name__ == "__main__":
    asyncio.run(clean_duplicates())
