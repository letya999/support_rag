from contextlib import asynccontextmanager
import psycopg
from psycopg_pool import AsyncConnectionPool
from app.settings import settings

_pool: AsyncConnectionPool | None = None

async def init_db_pool():
    """
    Initialize the global asynchronous connection pool for Postgres.
    Should be called during application startup.
    """
    global _pool
    # Create the pool
    _pool = AsyncConnectionPool(
        conninfo=str(settings.DATABASE_URL),
        min_size=5,
        max_size=20,
        open=False,
        kwargs={"autocommit": True}
    )
    # Open the pool
    await _pool.open()

async def close_db_pool():
    """
    Gracefully close the global asynchronous connection pool.
    Should be called during application shutdown.
    """
    global _pool
    if _pool:
        await _pool.close()

@asynccontextmanager
async def get_db_connection():
    """
    Async context manager for database connection using pool.
    
    Yields:
        psycopg.AsyncConnection: An asynchronous database connection
    """
    if _pool is None:
        # Fallback for scripts/tests that didn't call init_db_pool
        # But for prod default to error or auto-init?
        # Let's auto-init for safety if not running in app context, 
        # but optimal is explicit init. 
        # For now, simplistic lazy init to avoid breakage in scripts:
        await init_db_pool()
    
    async with _pool.connection() as conn:
        yield conn

def get_sync_db_connection():
    """
    Sync connection for non-async contexts (if needed).
    """
    return psycopg.connect(settings.DATABASE_URL, autocommit=True)
