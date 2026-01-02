"""Zero-shot classification service using transformers."""

import asyncio
import logging
from functools import lru_cache
from typing import Dict, Optional, Tuple

from transformers import pipeline

from app.nodes.classification.models import ClassificationOutput
from app.nodes.classification.prompts import INTENTS, CATEGORIES

logger = logging.getLogger(__name__)


class ClassificationService:
    """Zero-shot classifier using facebook/bart-large-mnli model."""

    def __init__(self):
        """Initialize the zero-shot classification pipeline."""
        logger.info("Loading zero-shot classification model...")
        try:
            self.pipe = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=0,  # Use GPU if available, else CPU
                multi_class=False,
            )
            logger.info("✅ Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

        self._cache: Dict[str, ClassificationOutput] = {}

    def _cache_key(self, question: str) -> str:
        """Generate cache key from question."""
        return hash(question) % ((sys.maxsize + 1) * 2)

    async def classify_intent(self, question: str) -> Tuple[str, float]:
        """
        Classify question into one of predefined intents.

        Args:
            question: User question

        Returns:
            Tuple of (intent, confidence)
        """
        try:
            result = await asyncio.to_thread(
                self.pipe,
                question,
                INTENTS,
            )
            intent = result["labels"][0]
            confidence = float(result["scores"][0])
            return intent, confidence
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return "faq", 0.0

    async def classify_category(
        self, question: str
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Classify question into one of predefined categories.

        Args:
            question: User question

        Returns:
            Tuple of (category, confidence, all_scores_dict)
        """
        try:
            result = await asyncio.to_thread(
                self.pipe,
                question,
                CATEGORIES,
            )

            category = result["labels"][0]
            confidence = float(result["scores"][0])

            # Create dict of all category scores
            all_scores = {
                cat: float(score)
                for cat, score in zip(result["labels"], result["scores"])
            }

            return category, confidence, all_scores
        except Exception as e:
            logger.error(f"Error classifying category: {e}")
            return "general", 0.0, {cat: 0.0 for cat in CATEGORIES}

    async def classify_both(self, question: str) -> ClassificationOutput:
        """
        Classify both intent and category.

        Args:
            question: User question

        Returns:
            ClassificationOutput with both intent and category
        """
        # Check cache first
        cache_key = self._cache_key(question)
        if cache_key in self._cache:
            logger.debug(f"Cache hit for question: {question[:50]}...")
            return self._cache[cache_key]

        # Run both classifications in parallel
        intent_task = asyncio.create_task(self.classify_intent(question))
        category_task = asyncio.create_task(self.classify_category(question))

        intent, intent_confidence = await intent_task
        category, category_confidence, all_category_scores = await category_task

        output = ClassificationOutput(
            intent=intent,
            intent_confidence=intent_confidence,
            category=category,
            category_confidence=category_confidence,
            all_category_scores=all_category_scores,
        )

        # Cache the result
        self._cache[cache_key] = output

        # Log classification
        logger.info(
            f"Classified question: intent={intent} ({intent_confidence:.2f}), "
            f"category={category} ({category_confidence:.2f})"
        )

        return output

    def clear_cache(self) -> None:
        """Clear the classification cache."""
        self._cache.clear()
        logger.debug("Classification cache cleared")


# Global singleton instance
_classification_service: Optional[ClassificationService] = None


def get_classification_service() -> ClassificationService:
    """Get or create the classification service singleton."""
    global _classification_service

    if _classification_service is None:
        _classification_service = ClassificationService()

    return _classification_service


# Add import sys for hash function
import sys
