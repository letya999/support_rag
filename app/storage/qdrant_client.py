from qdrant_client import QdrantClient, AsyncQdrantClient
from app.config.settings import settings

def get_qdrant_client() -> QdrantClient:
    """
    Get a synchronous Qdrant client.
    """
    return QdrantClient(url=settings.QDRANT_URL)

def get_async_qdrant_client() -> AsyncQdrantClient:
    """
    Get an asynchronous Qdrant client.
    """
    return AsyncQdrantClient(url=settings.QDRANT_URL)
