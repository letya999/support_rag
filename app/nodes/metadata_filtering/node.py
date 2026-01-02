"""Metadata filtering node for LangGraph pipeline."""

import logging
from typing import Any, Dict

from app.nodes.metadata_filtering.filtering import get_metadata_filtering_service
from app.observability.tracing import observe

logger = logging.getLogger(__name__)


@observe(as_type="span")
async def metadata_filter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Metadata filtering node with safety mechanisms.

    Input state:
        - question: str
        - category: Optional[str] - from classification
        - category_confidence: Optional[float] - from classification

    Output state:
        - docs: List[str] - retrieved (filtered or full search)
        - filter_used: bool
        - fallback_triggered: bool
        - filtering_reason: str
    """
    question = state.get("question", "")
    category = state.get("category")
    category_confidence = state.get("category_confidence", 0.0)

    if not question:
        logger.warning("Empty question in metadata_filter_node")
        return {
            "docs": [],
            "filter_used": False,
            "fallback_triggered": False,
            "filtering_reason": "Empty question",
        }

    service = get_metadata_filtering_service()

    try:
        result = await service.filter_and_search(
            question=question,
            category=category,
            category_confidence=category_confidence,
            top_k=3,
        )

        logger.info(
            f"Filtering result - filter_used: {result.filter_used}, "
            f"fallback: {result.fallback_triggered}, docs: {len(result.docs)}"
        )

        return {
            "docs": result.docs,
            "filter_used": result.filter_used,
            "fallback_triggered": result.fallback_triggered,
            "filtering_reason": result.reason,
        }
    except Exception as e:
        logger.error(f"Error in metadata_filter_node: {e}")
        return {
            "docs": [],
            "filter_used": False,
            "fallback_triggered": False,
            "filtering_reason": f"Error: {str(e)}",
        }
