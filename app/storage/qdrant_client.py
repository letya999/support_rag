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

def reset_async_qdrant_client():
    """
    Reset the async client singleton. 
    Useful when connection errors are detected (e.g. Channel closed).
    The next call to get_async_qdrant_client() will create a new connection.
    """
    global _async_client
    if _async_client:
        try:
             # Best effort close
             # Note: We can't await here easily if this is called from sync context,
             # but usually this is called from async context.
             # Ideally we should await _async_client.close() if possible.
             pass
        except Exception:
            pass
    _async_client = None
