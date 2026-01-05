"""
EmbeddingClassifier - Fast classification using semantic embeddings.

Uses the existing SemanticClassificationService to classify Q&A pairs
into categories and intents without any model training.
"""

import asyncio
from typing import Dict, List, Optional
from app.nodes.easy_classification.semantic_classifier import SemanticClassificationService
from app.integrations.embeddings import get_embedding
from .models import ClassificationResult, MetadataConfig


class EmbeddingClassifier:
    """
    Classifies Q&A pairs using semantic embeddings and cosine similarity.

    No training required - uses pre-trained SemanticTransformer embeddings.
    """

    def __init__(self, config: Optional[MetadataConfig] = None):
        """Initialize classifier with configuration."""
        self.config = config or MetadataConfig()
        self.classifier = SemanticClassificationService()
        self.is_ready = False

    async def initialize(self):
        """Initialize the classifier (load models if needed)."""
        await self.classifier._ensure_model()
        self.is_ready = True

    async def classify(
        self,
        question: str,
        answer: str
    ) -> Dict[str, ClassificationResult]:
        """
        Classify a Q&A pair into category and intent.

        Args:
            question: The question text
            answer: The answer text

        Returns:
            Dict with 'category' and 'intent' classification results
        """
        if not self.is_ready:
            await self.initialize()

        # Get classification from semantic classifier
        classification = await self.classifier.classify(question)

        if classification is None:
            # Fallback if classification fails
            return {
                "category": ClassificationResult(
                    category="unknown",
                    confidence=0.0,
                    method="fallback",
                    needs_llm_validation=True
                ),
                "intent": ClassificationResult(
                    category="unknown",
                    confidence=0.0,
                    method="fallback",
                    needs_llm_validation=True
                )
            }

        # Determine if LLM validation is needed
        category_needs_validation = (
            classification.category_confidence < self.config.confidence_threshold_high
        )
        intent_needs_validation = (
            classification.intent_confidence < self.config.confidence_threshold_low
        )

        return {
            "category": ClassificationResult(
                category=classification.category,
                confidence=classification.category_confidence,
                method="embedding",
                needs_llm_validation=category_needs_validation
            ),
            "intent": ClassificationResult(
                category=classification.intent,
                confidence=classification.intent_confidence,
                method="embedding",
                needs_llm_validation=intent_needs_validation
            )
        }

    async def classify_batch(
        self,
        qa_pairs: List[Dict[str, str]]
    ) -> List[Dict[str, ClassificationResult]]:
        """
        Classify a batch of Q&A pairs in parallel.

        Args:
            qa_pairs: List of {"question": "...", "answer": "..."} dicts

        Returns:
            List of classification results
        """
        if not self.is_ready:
            await self.initialize()

        # Classify all pairs in parallel
        tasks = [
            self.classify(pair["question"], pair["answer"])
            for pair in qa_pairs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error classifying pair {idx}: {result}")
                # Return fallback
                processed_results.append({
                    "category": ClassificationResult(
                        category="unknown",
                        confidence=0.0,
                        method="fallback",
                        needs_llm_validation=True
                    ),
                    "intent": ClassificationResult(
                        category="unknown",
                        confidence=0.0,
                        method="fallback",
                        needs_llm_validation=True
                    )
                })
            else:
                processed_results.append(result)

        return processed_results

    def get_summary_stats(
        self,
        classification_results: List[Dict[str, ClassificationResult]]
    ) -> Dict:
        """Calculate statistics from classification results."""
        category_confidences = []
        intent_confidences = []
        llm_validations_needed = 0

        for result in classification_results:
            cat_result = result.get("category")
            intent_result = result.get("intent")

            if cat_result:
                category_confidences.append(cat_result.confidence)
                if cat_result.needs_llm_validation:
                    llm_validations_needed += 1

            if intent_result:
                intent_confidences.append(intent_result.confidence)

        return {
            "avg_category_confidence": (
                sum(category_confidences) / len(category_confidences)
                if category_confidences
                else 0.0
            ),
            "avg_intent_confidence": (
                sum(intent_confidences) / len(intent_confidences)
                if intent_confidences
                else 0.0
            ),
            "llm_validations_needed": llm_validations_needed,
            "llm_percentage": (
                (llm_validations_needed / len(classification_results)) * 100
                if classification_results
                else 0.0
            ),
            "embedding_percentage": (
                ((len(classification_results) - llm_validations_needed) / len(classification_results)) * 100
                if classification_results
                else 0.0
            )
        }
