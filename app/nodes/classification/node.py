"""Classification node for LangGraph pipeline."""

import logging
from typing import Any, Dict

from app.nodes.classification.classifier import get_classification_service
from app.observability.tracing import observe

logger = logging.getLogger(__name__)


@observe(as_type="span")
async def classify_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for intent and category classification.

    Input state:
        - question: str - User's question

    Output state:
        - intent: str
        - intent_confidence: float
        - category: str
        - category_confidence: float
        - all_category_scores: Dict[str, float]
    """
    question = state.get("question", "")

    if not question:
        logger.warning("Empty question in classify_node")
        return {
            "intent": "general",
            "intent_confidence": 0.0,
            "category": "general",
            "category_confidence": 0.0,
            "all_category_scores": {},
        }

    service = get_classification_service()

    try:
        result = await service.classify_both(question)

        return {
            "intent": result.intent,
            "intent_confidence": result.intent_confidence,
            "category": result.category,
            "category_confidence": result.category_confidence,
            "all_category_scores": result.all_category_scores,
        }
    except Exception as e:
        logger.error(f"Error in classify_node: {e}")
        return {
            "intent": "general",
            "intent_confidence": 0.0,
            "category": "general",
            "category_confidence": 0.0,
            "all_category_scores": {},
        }
