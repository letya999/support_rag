from typing import Optional
from langfuse import Langfuse
from app.settings import settings

_client: Optional[Langfuse] = None

def get_langfuse_client() -> Optional[Langfuse]:
    """
    Get or initialize Langfuse client singleton.
    """
    global _client
    if _client:
        return _client
        
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        _client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST
        )
    return _client

def flush_langfuse():
    """Flush Langfuse events."""
    if _client:
        _client.flush()
