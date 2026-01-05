from qdrant_client import QdrantClient, AsyncQdrantClient
from app.settings import settings

def get_qdrant_client() -> QdrantClient:
    """
    Get a synchronous Qdrant client.
    """
    return QdrantClient(url=settings.QDRANT_URL)

_async_client = None

def get_async_qdrant_client() -> AsyncQdrantClient:
    """
    Get an asynchronous Qdrant client metadata.
    Uses a singleton pattern to avoid creating multiple clients/connections.
    Optimized for performance with gRPC.
    """
    global _async_client
    if _async_client is None:
        _async_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            prefer_grpc=True,
            grpc_options={
                "grpc.max_receive_message_length": 50 * 1024 * 1024,
            }
        )
    return _async_client
