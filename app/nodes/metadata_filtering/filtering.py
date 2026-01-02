"""Metadata filtering service with safety mechanisms."""

import logging
from typing import List, Optional, Dict, Any

from app.integrations.embeddings import get_embedding
from app.storage.vector_store import search_documents
from app.nodes.metadata_filtering.models import FilteringOutput

logger = logging.getLogger(__name__)


class MetadataFilteringService:
    """Service for filtering documents by category with safety fallback."""

    def __init__(
        self,
        safety_threshold: float = 0.5,
        min_results_for_filter: int = 2,
    ):
        """
        Initialize filtering service.

        Args:
            safety_threshold: Minimum category_confidence to apply filter
            min_results_for_filter: Minimum results required before fallback
        """
        self.safety_threshold = safety_threshold
        self.min_results_for_filter = min_results_for_filter

    async def filter_and_search(
        self,
        question: str,
        category: Optional[str] = None,
        category_confidence: float = 0.0,
        top_k: int = 3,
    ) -> FilteringOutput:
        """
        Smart filtering with safety mechanisms.

        Logic:
        1. If category_confidence < safety_threshold → skip filtering
        2. If retrieve from category AND found >= min_results → use filtered
        3. If retrieve from category AND found < min_results → FALLBACK to all
        4. Else → return all documents

        Args:
            question: User question
            category: Classified category (e.g., "billing", "shipping")
            category_confidence: Confidence of category classification (0.0-1.0)
            top_k: Number of documents to retrieve

        Returns:
            FilteringOutput with docs and metadata about filtering decision
        """

        # Step 1: Check if we should use filtering at all
        if category_confidence < self.safety_threshold:
            logger.info(
                f"Low category confidence ({category_confidence:.2f}) < "
                f"threshold ({self.safety_threshold}). Skipping filter."
            )
            results = await self._retrieve_all(question, top_k)
            return FilteringOutput(
                docs=[d.content for d in results],
                docs_with_metadata=[
                    {
                        "content": d.content,
                        "score": d.score,
                        "metadata": d.metadata,
                    }
                    for d in results
                ],
                filter_used=False,
                fallback_triggered=False,
                reason="Low category confidence - no filtering applied",
                category_docs_count=None,
                total_docs_searched=len(results),
            )

        # Step 2: Try to retrieve from category
        if category:
            logger.info(f"Attempting filtered search for category: {category}")

            filtered_results = await self._retrieve_by_category(
                question, category, top_k
            )

            if len(filtered_results) >= self.min_results_for_filter:
                logger.info(
                    f"Filter succeeded: found {len(filtered_results)} docs in {category}"
                )
                return FilteringOutput(
                    docs=[d.content for d in filtered_results],
                    docs_with_metadata=[
                        {
                            "content": d.content,
                            "score": d.score,
                            "metadata": d.metadata,
                        }
                        for d in filtered_results
                    ],
                    filter_used=True,
                    fallback_triggered=False,
                    reason=f"Filtered by category '{category}' - found {len(filtered_results)} docs",
                    category_docs_count=len(filtered_results),
                    total_docs_searched=len(filtered_results),
                )
            else:
                # Not enough results - FALLBACK
                logger.warning(
                    f"Filter fallback triggered: only {len(filtered_results)} docs "
                    f"in '{category}' (min required: {self.min_results_for_filter}). "
                    f"Falling back to full search."
                )
                all_results = await self._retrieve_all(question, top_k)
                return FilteringOutput(
                    docs=[d.content for d in all_results],
                    docs_with_metadata=[
                        {
                            "content": d.content,
                            "score": d.score,
                            "metadata": d.metadata,
                        }
                        for d in all_results
                    ],
                    filter_used=True,
                    fallback_triggered=True,
                    reason=(
                        f"Filter fallback: '{category}' had only {len(filtered_results)} docs, "
                        f"using full search instead"
                    ),
                    category_docs_count=len(filtered_results),
                    total_docs_searched=len(all_results),
                )

        # Step 3: No category - retrieve all
        logger.info("No category provided - searching all documents")
        results = await self._retrieve_all(question, top_k)
        return FilteringOutput(
            docs=[d.content for d in results],
            docs_with_metadata=[
                {
                    "content": d.content,
                    "score": d.score,
                    "metadata": d.metadata,
                }
                for d in results
            ],
            filter_used=False,
            fallback_triggered=False,
            reason="No category provided - searching all documents",
            category_docs_count=None,
            total_docs_searched=len(results),
        )

    async def _retrieve_by_category(
        self, question: str, category: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents for specific category.

        Args:
            question: User question
            category: Category name (e.g., "billing")
            top_k: Number of results

        Returns:
            List of search results with metadata
        """
        try:
            embedding = await get_embedding(question)
            results = await search_documents(
                embedding, category_filter=category, top_k=top_k
            )
            return results
        except Exception as e:
            logger.error(f"Error retrieving by category '{category}': {e}")
            return []

    async def _retrieve_all(
        self, question: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve from all documents (no category filter).

        Args:
            question: User question
            top_k: Number of results

        Returns:
            List of search results with metadata
        """
        try:
            embedding = await get_embedding(question)
            results = await search_documents(
                embedding, category_filter=None, top_k=top_k
            )
            return results
        except Exception as e:
            logger.error(f"Error retrieving all documents: {e}")
            return []


# Global singleton instance
_filtering_service: Optional[MetadataFilteringService] = None


def get_metadata_filtering_service() -> MetadataFilteringService:
    """Get or create the metadata filtering service singleton."""
    global _filtering_service

    if _filtering_service is None:
        _filtering_service = MetadataFilteringService()

    return _filtering_service


# Import at end to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.vector_store import SearchResult
