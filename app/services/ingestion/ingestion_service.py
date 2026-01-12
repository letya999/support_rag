"""Service for ingesting Q&A pairs into PostgreSQL and Qdrant."""

import json
import logging
from typing import List

import psycopg
from qdrant_client.http import models

from app.settings import settings
from app.integrations.embeddings_opensource import get_embeddings_batch
from app.services.document_loaders import ProcessedQAPair
from app.storage.qdrant_client import get_async_qdrant_client

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """Service for ingesting Q&A pairs into vector store and database."""

    BATCH_SIZE = 32
    COLLECTION_NAME = "documents"
    VECTOR_SIZE = 384

    @staticmethod
    async def ingest_pairs(pairs: List[ProcessedQAPair], recreate_collection: bool = False) -> dict:
        """Ingest Q&A pairs into PostgreSQL and Qdrant.

        Args:
            pairs: List of processed Q&A pairs
            recreate_collection: If True, recreate Qdrant collection

        Returns:
            Dict with ingestion results
        """
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set")

        if not pairs:
            logger.warning("No pairs to ingest")
            return {"status": "success", "ingested_count": 0}

        logger.info(f"Starting ingestion of {len(pairs)} Q&A pairs")

        # Initialize Qdrant
        qdrant = get_async_qdrant_client()
        collection_name = DocumentIngestionService.COLLECTION_NAME

        try:
            # Recreate collection if requested
            if recreate_collection:
                try:
                    await qdrant.delete_collection(collection_name)
                except Exception:
                    pass  # Collection might not exist

                await qdrant.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=DocumentIngestionService.VECTOR_SIZE,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Recreated Qdrant collection: {collection_name}")
            else:
                # Ensure collection exists
                try:
                    await qdrant.get_collection(collection_name)
                except Exception:
                    # Create if doesn't exist
                    await qdrant.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=DocumentIngestionService.VECTOR_SIZE,
                            distance=models.Distance.COSINE
                        )
                    )
                    logger.info(f"Created new Qdrant collection: {collection_name}")

        except Exception as e:
            logger.error(f"Error initializing Qdrant: {e}")
            raise

        ingested_count = 0

        try:
            # Use async connection
            async with await psycopg.AsyncConnection.connect(
                settings.DATABASE_URL, autocommit=True
            ) as conn:
                async with conn.cursor() as cur:
                    # Ensure table exists
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS documents (
                            id SERIAL PRIMARY KEY,
                            content TEXT NOT NULL,
                            embedding vector(384),
                            metadata JSONB
                        );
                    """)

                    # Add FTS indices if they don't exist
                    try:
                        await cur.execute(
                            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                            "fts_en tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;"
                        )
                        await cur.execute(
                            "CREATE INDEX IF NOT EXISTS idx_documents_fts_en ON documents USING GIN (fts_en);"
                        )
                    except Exception as e:
                        logger.warning(f"Could not setup English FTS: {e}")

                    try:
                        await cur.execute(
                            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS "
                            "fts_ru tsvector GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED;"
                        )
                        await cur.execute(
                            "CREATE INDEX IF NOT EXISTS idx_documents_fts_ru ON documents USING GIN (fts_ru);"
                        )
                    except Exception as e:
                        logger.warning(f"Could not setup Russian FTS: {e}")

                    # Process in batches
                    for i in range(0, len(pairs), DocumentIngestionService.BATCH_SIZE):
                        batch = pairs[i : i + DocumentIngestionService.BATCH_SIZE]
                        batch_num = i // DocumentIngestionService.BATCH_SIZE + 1
                        total_batches = (len(pairs) + DocumentIngestionService.BATCH_SIZE - 1) // DocumentIngestionService.BATCH_SIZE

                        logger.info(f"Processing batch {batch_num}/{total_batches}...")

                        # Prepare batch content
                        batch_contents = []
                        batch_metadatas = []

                        for pair in batch:
                            content = f"Question: {pair.question}\nAnswer: {pair.answer}"
                            batch_contents.append(content)
                            batch_metadatas.append(pair.metadata)

                        # Generate embeddings
                        embeddings = await get_embeddings_batch(batch_contents)

                        # Insert into PostgreSQL and prepare Qdrant points
                        points = []

                        for content, embedding, metadata in zip(
                            batch_contents, embeddings, batch_metadatas
                        ):
                            metadata_json = json.dumps(metadata)

                            # Check for duplicates
                            await cur.execute(
                                "SELECT id FROM documents WHERE content = %s",
                                (content,)
                            )
                            existing = await cur.fetchone()
                            
                            if existing:
                                logger.warning(f"Skipping duplicate content: {content[:50]}...")
                                # Optionally, we could update metadata here if needed, 
                                # but for now we just skip to prevent duplication.
                                continue

                            # Insert into PostgreSQL
                            await cur.execute(
                                """
                                INSERT INTO documents (content, embedding, metadata)
                                VALUES (%s, %s, %s)
                                RETURNING id
                                """,
                                (content, embedding, metadata_json)
                            )
                            row = await cur.fetchone()
                            doc_id = row[0]

                            # Prepare Qdrant point
                            qdrant_payload = {
                                "category": metadata.get("category"),
                                "intent": metadata.get("intent"),
                                "source": "multi_format_ingest"
                            }

                            points.append(
                                models.PointStruct(
                                    id=doc_id,
                                    vector=embedding,
                                    payload=qdrant_payload
                                )
                            )

                            ingested_count += 1

                        # Upsert batch to Qdrant
                        if points:
                            await qdrant.upsert(
                                collection_name=collection_name,
                                points=points
                            )

                logger.info(
                    f"Ingestion complete! {ingested_count} documents stored in "
                    f"PostgreSQL and Qdrant"
                )

        except Exception as e:
            logger.error(f"Error during ingestion: {e}")
            raise
        finally:
            # Close Qdrant client if it has close method
            if hasattr(qdrant, "close"):
                await qdrant.close()

        return {
            "status": "success",
            "ingested_count": ingested_count
        }
