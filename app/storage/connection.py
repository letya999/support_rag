from contextlib import asynccontextmanager
import psycopg
from app.config.settings import settings

@asynccontextmanager
async def get_db_connection():
    """
    Async context manager for database connection.
    """
    conn = await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True)
    try:
        yield conn
    finally:
        await conn.close()

def get_sync_db_connection():
    """
    Sync connection for non-async contexts (if needed).
    """
    return psycopg.connect(settings.DATABASE_URL, autocommit=True)
