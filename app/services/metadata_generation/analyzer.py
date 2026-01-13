"""
HybridMetadataAnalyzer - Main orchestrator for metadata generation.

Coordinates embedding classification, LLM validation, and handoff detection.
"""

import asyncio
import time
from typing import Dict, List, Optional
from app.logging_config import logger
from .embedding_classifier import EmbeddingClassifier
from .context_retriever import ContextRetriever
from .llm_validator import LLMValidator
from .handoff_detector import HandoffDetector
from .models import (
    MetadataConfig,
    QAPairMetadata,
    QAPairWithMetadata,
    AnalysisResult,
    AnalysisStats
)


class HybridMetadataAnalyzer:
    """
    Main orchestrator for hybrid metadata generation.

    Flow:
    1. Fast embedding classification (no training)
    2. LLM validation for low-confidence predictions
    3. Handoff detection
    4. Merge results
    """

    def __init__(self, config: Optional[MetadataConfig] = None):
        """Initialize analyzer with configuration."""
        self.config = config or MetadataConfig()
        self.classifier = EmbeddingClassifier(config)
        self.context_retriever = ContextRetriever(config)
        self.llm_validator = LLMValidator(config)
        self.handoff_detector = HandoffDetector()

    async def initialize(self):
        """Initialize all components."""
        await self.classifier.initialize()

    async def analyze_batch(
        self,
        qa_pairs: List[Dict[str, str]],
        analysis_id: str
    ) -> AnalysisResult:
        """
        Analyze a batch of Q&A pairs.

        Args:
            qa_pairs (List[Dict[str, str]]): List of {"question": "...", "answer": "..."} dicts.
            analysis_id (str): Unique ID for this analysis.

        Returns:
            AnalysisResult: Object containing all metadata and statistics.
        """
        start_time = time.time()

        # Ensure classifier is initialized
        if not self.classifier.is_ready:
            await self.initialize()

        # Step 1: Fast embedding classification
        logger.info("Analyzer Step 1: Embedding classification", extra={"count": len(qa_pairs), "analysis_id": analysis_id})
        classification_results = await self.classifier.classify_batch(qa_pairs)

        # Step 2: Identify pairs needing LLM validation
        pairs_needing_validation = []
        for idx, (qa, clf_result) in enumerate(zip(qa_pairs, classification_results)):
            if clf_result["category"].needs_llm_validation:
                pairs_needing_validation.append({
                    "qa_index": idx,
                    "qa": qa,
                    "clf_result": clf_result
                })
        
        logger.info("Analyzer uncertainty check", extra={"needs_validation": len(pairs_needing_validation)})

        # Step 3: LLM validation for low-confidence pairs
        llm_results = {}
        if pairs_needing_validation:
            logger.info("Analyzer Step 2: LLM validation started")
            llm_results = await self._validate_with_llm(pairs_needing_validation)

        # Step 4: Handoff detection (parallel)
        logger.info("Analyzer Step 3: Handoff detection")
        handoff_results = self.handoff_detector.detect_batch(qa_pairs)

        # Step 5: Merge results
        logger.info("Analyzer Step 4: Merging results")
        qa_with_metadata = self._merge_results(
            qa_pairs,
            classification_results,
            llm_results,
            handoff_results
        )

        # Step 6: Compute statistics
        processing_time = time.time() - start_time
        stats = self._compute_statistics(
            qa_with_metadata,
            classification_results,
            llm_results,
            handoff_results,
            processing_time
        )

        return AnalysisResult(
            analysis_id=analysis_id,
            total_pairs=len(qa_pairs),
            high_confidence_count=len(qa_pairs) - len(pairs_needing_validation),
            low_confidence_count=len(pairs_needing_validation),
            llm_validated_count=len(llm_results),
            qa_with_metadata=qa_with_metadata,
            statistics=stats
        )

    async def _validate_with_llm(
        self,
        pairs_needing_validation: List[Dict]
    ) -> Dict[int, Dict]:
        """Validate low-confidence predictions with LLM."""
        validation_requests = []

        for item in pairs_needing_validation:
            qa_index = item["qa_index"]
            qa = item["qa"]
            clf_result = item["clf_result"]
            predicted_category = clf_result["category"].category

            # Get context
            context = await self.context_retriever.get_category_examples(
                predicted_category
            )

            # Build validation request
            validation_requests.append({
                "type": "category",
                "qa_index": qa_index,
                "question": qa["question"],
                "predicted_category": predicted_category,
                "confidence": clf_result["category"].confidence,
                "context": context
            })

        # Validate in parallel batches
        llm_validation_results = await self.llm_validator.validate_batch(
            validation_requests
        )

        # Convert to dict indexed by qa_index
        llm_results = {}
        for result in llm_validation_results:
            qa_idx = result.pop("qa_index")
            llm_results[qa_idx] = result

        return llm_results

    def _merge_results(
        self,
        qa_pairs: List[Dict[str, str]],
        classification_results: List[Dict],
        llm_results: Dict[int, Dict],
        handoff_results: List[Dict]
    ) -> List[QAPairWithMetadata]:
        """Merge all results into final metadata."""
        qa_with_metadata = []

        for idx, (qa, clf_result, handoff_result) in enumerate(
            zip(qa_pairs, classification_results, handoff_results)
        ):
            # Get category (from LLM if validated, otherwise from embedding)
            if idx in llm_results:
                category = llm_results[idx].get(
                    "suggested_category",
                    clf_result["category"].category
                )
                category_confidence = llm_results[idx].get(
                    "confidence",
                    clf_result["category"].confidence
                )
                validation_method = "llm"
            else:
                category = clf_result["category"].category
                category_confidence = clf_result["category"].confidence
                validation_method = "embedding"

            # Get intent (always from embedding for now)
            intent = clf_result["intent"].category
            intent_confidence = clf_result["intent"].confidence

            # Build metadata
            metadata = QAPairMetadata(
                category=category,
                intent=intent,
                requires_handoff=handoff_result["requires_handoff"],
                confidence_threshold=handoff_result["confidence_threshold"],
                clarifying_questions=handoff_result["clarifying_questions"],
                confidence_scores={
                    "category": category_confidence,
                    "intent": intent_confidence,
                    "validation_method": validation_method
                }
            )

            qa_with_metadata.append(
                QAPairWithMetadata(
                    qa_index=idx,
                    question=qa["question"],
                    answer=qa["answer"],
                    metadata=metadata
                )
            )

        return qa_with_metadata

    def _compute_statistics(
        self,
        qa_with_metadata: List[QAPairWithMetadata],
        classification_results: List[Dict],
        llm_results: Dict[int, Dict],
        handoff_results: List[Dict],
        processing_time: float
    ) -> Dict:
        """Compute analysis statistics."""
        # Category confidence
        category_confidences = [
            qa.metadata.confidence_scores["category"]
            for qa in qa_with_metadata
        ]

        # Intent confidence
        intent_confidences = [
            qa.metadata.confidence_scores["intent"]
            for qa in qa_with_metadata
        ]

        # Handoff count
        handoff_count = sum(
            1 for qa in qa_with_metadata if qa.metadata.requires_handoff
        )

        # Methods used
        embedding_count = sum(
            1 for qa in qa_with_metadata
            if qa.metadata.confidence_scores.get("validation_method") == "embedding"
        )
        llm_count = sum(
            1 for qa in qa_with_metadata
            if qa.metadata.confidence_scores.get("validation_method") == "llm"
        )

        return {
            "total_items": len(qa_with_metadata),
            "embedding_classified": embedding_count,
            "llm_validated": llm_count,
            "embedding_percentage": (
                (embedding_count / len(qa_with_metadata)) * 100
                if qa_with_metadata
                else 0.0
            ),
            "llm_percentage": (
                (llm_count / len(qa_with_metadata)) * 100
                if qa_with_metadata
                else 0.0
            ),
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
            "handoff_count": handoff_count,
            "handoff_percentage": (
                (handoff_count / len(qa_with_metadata)) * 100
                if qa_with_metadata
                else 0.0
            ),
            "processing_time_seconds": round(processing_time, 2),
            "average_time_per_pair_ms": round((processing_time / len(qa_with_metadata)) * 1000, 2)
        }
