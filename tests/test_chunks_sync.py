
import asyncio
import json
import logging
import psycopg
from qdrant_client.http import models
from app.settings import settings
from app.storage import qdrant_client as qc_module
from qdrant_client import AsyncQdrantClient
from app.services.chunk_service import chunk_service
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test_chunk_sync():
    logger.info("Starting Chunk Service Sync Test...")
    
    # PATCH: Ensure we have a working client for the test environment
    # Explicitly set grpc_port to 6334 which is exposed in docker-compose
    logger.info(f"Test loaded setting QDRANT_URL: {settings.QDRANT_URL}")
    
    # We force a fresh client with correct local config for the test
    # This proves the logic works given a valid client
    test_client = AsyncQdrantClient(
        url="http://localhost:6333",
        prefer_grpc=True,
        grpc_port=6334,
    )
    # Inject into the singleton
    qc_module._async_client = test_client

    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL not set")
        return

    # 1. Setup Test Data
    test_content = "Test Content for Sync Check"
    test_metadata = {"intent": "test_intent", "category": "test_category", "requires_handoff": False}
    # Dummy embedding (size 384 as per ingestion service)
    test_embedding = [0.1] * 384 

    conn = await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True)
    async with conn:
        async with conn.cursor() as cur:
            # Insert into Postgres
            await cur.execute(
                "INSERT INTO documents (content, embedding, metadata) VALUES (%s, %s, %s) RETURNING id",
                (test_content, str(test_embedding), json.dumps(test_metadata))
            )
            row = await cur.fetchone()
            doc_id = row[0]
            logger.info(f"Created Test Document in PG with ID: {doc_id}")

    # Insert into Qdrant
    qdrant = qc_module.get_async_qdrant_client()
    try:
        await qdrant.upsert(
            collection_name="documents",
            points=[
                models.PointStruct(
                    id=doc_id,
                    vector=test_embedding,
                    payload=test_metadata
                )
            ]
        )
        logger.info(f"Created Test Point in Qdrant with ID: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to setup Qdrant: {e}")
        return

    try:
        # 2. Test List/Get
        logger.info("Testing List Chunks...")
        chunks = await chunk_service.list_chunks(chunk_id=doc_id)
        if chunks["total"] == 1 and chunks["items"][0]["id"] == doc_id:
            logger.info("SUCCESS: list_chunks found the document.")
        else:
            logger.error(f"FAILURE: list_chunks did not find the document correctly. Result: {chunks}")

        # 3. Test Update
        logger.info("Testing Update Chunk (Metadata)...")
        new_metadata_update = {"intent": "updated_intent", "requires_handoff": True}
        
        # Expected merged metadata
        expected_metadata = test_metadata.copy()
        expected_metadata.update(new_metadata_update)

        await chunk_service.update_chunk(doc_id, metadata=new_metadata_update)

        # Verify PG
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as check_conn:
            async with check_conn.cursor() as check_cur:
                 await check_cur.execute("SELECT metadata FROM documents WHERE id = %s", (doc_id,))
                 pg_row = await check_cur.fetchone()
                 pg_meta = pg_row[0]
                 if pg_meta.get("intent") == "updated_intent" and pg_meta.get("requires_handoff") is True:
                     logger.info("SUCCESS: Postgres metadata updated.")
                 else:
                     logger.error(f"FAILURE: Postgres metadata mismatch. Got: {pg_meta}")

        # Verify Qdrant
        q_points = await qdrant.retrieve(
            collection_name="documents",
            ids=[doc_id],
            with_payload=True
        )
        if q_points:
            q_payload = q_points[0].payload
            if q_payload.get("intent") == "updated_intent" and q_payload.get("requires_handoff") is True:
                 logger.info("SUCCESS: Qdrant payload updated.")
            else:
                 logger.error(f"FAILURE: Qdrant payload mismatch. Got: {q_payload}")
        else:
            logger.error("FAILURE: Could not retrieve point from Qdrant.")

        # 4. Test Delete
        logger.info("Testing Delete Chunk...")
        await chunk_service.delete_chunk(doc_id)

        # Verify PG
        async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as check_conn:
            async with check_conn.cursor() as check_cur:
                 await check_cur.execute("SELECT id FROM documents WHERE id = %s", (doc_id,))
                 pg_row = await check_cur.fetchone()
                 if not pg_row:
                     logger.info("SUCCESS: Document deleted from Postgres.")
                 else:
                     logger.error("FAILURE: Document still exists in Postgres.")

        # Verify Qdrant
        q_points_after = await qdrant.retrieve(
            collection_name="documents",
            ids=[doc_id]
        )
        if not q_points_after:
             logger.info("SUCCESS: Point deleted from Qdrant.")
        else:
             logger.error("FAILURE: Point still exists in Qdrant.")

    finally:
        # Cleanup (just in case delete failed, though test data is somewhat persistent if we crash)
         pass

if __name__ == "__main__":
    asyncio.run(test_chunk_sync())
