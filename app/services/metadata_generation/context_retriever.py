"""
ContextRetriever - Fetch example Q&A pairs from database for LLM context.

Retrieves similar questions and answer chunks to provide context for LLM validation.
"""

from typing import List, Dict, Optional
from sqlalchemy import text
from app.storage.connection import get_sync_db_connection
from .models import ContextExample, CategoryContext, MetadataConfig


class ContextRetriever:
    """
    Retrieves context examples from database for LLM validation.

    Fetches similar questions and answer chunks from a specific category
    to provide examples for the LLM validator.
    """

    def __init__(self, config: Optional[MetadataConfig] = None):
        """Initialize context retriever."""
        self.config = config or MetadataConfig()
        self.db = get_sync_db_connection()
        self._context_cache = {}

    async def get_category_examples(
        self,
        category: str,
        limit: Optional[int] = None
    ) -> CategoryContext:
        """
        Get example questions from a category.

        Args:
            category: Category name
            limit: Number of examples to retrieve (uses config default if None)

        Returns:
            CategoryContext with example questions
        """
        if limit is None:
            limit = self.config.context_examples_count

        # Check cache
        cache_key = f"category_examples:{category}:{limit}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        try:
            query = text("""
                SELECT content, metadata
                FROM documents
                WHERE metadata->>'category' = :category
                AND content IS NOT NULL
                ORDER BY created_at DESC
                LIMIT :limit
            """)

            results = self.db.execute(
                query,
                {"category": category, "limit": limit}
            ).fetchall()

            examples = [
                ContextExample(
                    content=result[0][:300] if result[0] else "",  # Limit to 300 chars
                    metadata=result[1] if len(result) > 1 else None
                )
                for result in results
            ]

            context = CategoryContext(
                category=category,
                examples=examples
            )

            # Cache the result
            self._context_cache[cache_key] = context

            return context

        except Exception as e:
            print(f"Error retrieving category examples for '{category}': {e}")
            return CategoryContext(category=category, examples=[])

    async def get_category_chunks(
        self,
        category: str,
        limit: Optional[int] = None
    ) -> CategoryContext:
        """
        Get answer chunks (preview) from a category.

        Args:
            category: Category name
            limit: Number of chunks to retrieve (uses config default if None)

        Returns:
            CategoryContext with example chunks
        """
        if limit is None:
            limit = self.config.context_chunks_count

        # Check cache
        cache_key = f"category_chunks:{category}:{limit}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        try:
            query = text("""
                SELECT
                    LEFT(content, :chunk_length) as chunk,
                    metadata
                FROM documents
                WHERE metadata->>'category' = :category
                AND content IS NOT NULL
                ORDER BY char_length(content) DESC
                LIMIT :limit
            """)

            results = self.db.execute(
                query,
                {
                    "category": category,
                    "limit": limit,
                    "chunk_length": self.config.chunk_preview_length
                }
            ).fetchall()

            examples = [
                ContextExample(
                    content=result[0] if result[0] else "",
                    metadata=result[1] if len(result) > 1 else None
                )
                for result in results
            ]

            context = CategoryContext(
                category=category,
                examples=examples
            )

            # Cache the result
            self._context_cache[cache_key] = context

            return context

        except Exception as e:
            print(f"Error retrieving category chunks for '{category}': {e}")
            return CategoryContext(category=category, examples=[])

    async def get_intent_examples(
        self,
        category: str,
        intent: str,
        limit: Optional[int] = None
    ) -> CategoryContext:
        """
        Get example questions for a specific intent within a category.

        Args:
            category: Parent category name
            intent: Intent name
            limit: Number of examples

        Returns:
            CategoryContext with example questions for intent
        """
        if limit is None:
            limit = self.config.context_examples_count

        cache_key = f"intent_examples:{category}:{intent}:{limit}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        try:
            query = text("""
                SELECT content, metadata
                FROM documents
                WHERE metadata->>'category' = :category
                AND metadata->>'intent' = :intent
                AND content IS NOT NULL
                ORDER BY created_at DESC
                LIMIT :limit
            """)

            results = self.db.execute(
                query,
                {
                    "category": category,
                    "intent": intent,
                    "limit": limit
                }
            ).fetchall()

            examples = [
                ContextExample(
                    content=result[0][:300] if result[0] else "",
                    metadata=result[1] if len(result) > 1 else None
                )
                for result in results
            ]

            context = CategoryContext(
                category=f"{category}/{intent}",
                examples=examples
            )

            self._context_cache[cache_key] = context
            return context

        except Exception as e:
            print(f"Error retrieving intent examples for '{category}/{intent}': {e}")
            return CategoryContext(category=f"{category}/{intent}", examples=[])

    def clear_cache(self):
        """Clear the context cache."""
        self._context_cache.clear()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cached_contexts": len(self._context_cache),
            "cache_keys": list(self._context_cache.keys())
        }
