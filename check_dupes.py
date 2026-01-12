import asyncio
import os
import sys

# Add app to path
sys.path.append(os.getcwd())

from app.storage.connection import get_db_connection

async def check_duplicates():
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            # Check for specific content duplication
            target_content_start = "Question: Как вернуть деньги за подписку?"
            query = """
                SELECT count(*), content
                FROM documents
                WHERE content LIKE %s
                GROUP BY content
                HAVING count(*) > 1;
            """
            await cur.execute(query, (target_content_start + '%',))
            rows = await cur.fetchall()
            
            if rows:
                print(f"FOUND DUPLICATES:")
                for count, content in rows:
                    print(f"Count: {count}")
                    print(f"Content Start: {content[:100]}...")
            else:
                print("No exact content duplicates found for this query.")
                
            # Also check total duplicates
            print("\nChecking total duplicate count in documents table...")
            await cur.execute("SELECT count(*) FROM documents")
            total = (await cur.fetchone())[0]
            
            await cur.execute("SELECT count(DISTINCT content) FROM documents")
            distinct = (await cur.fetchone())[0]
            
            print(f"Total rows: {total}")
            print(f"Distinct contents: {distinct}")
            print(f"Duplicates: {total - distinct}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_duplicates())
