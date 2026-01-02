from app.storage.connection import get_db_connection
from app.observability.langfuse_client import get_langfuse_client

async def get_db():
    async with get_db_connection() as conn:
        yield conn

def get_langfuse():
    return get_langfuse_client()
