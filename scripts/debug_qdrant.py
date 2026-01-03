import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

async def main():
    client = AsyncQdrantClient(url="http://localhost:6333")
    print("Attributes of AsyncQdrantClient:")
    print([d for d in dir(client) if not d.startswith("_")])
    
    try:
        # Try to verify if search is callable even if not in dir (doubtful)
        print(f"Has search? {hasattr(client, 'search')}")
    except Exception as e:
        print(f"Error checking search: {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
