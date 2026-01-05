"""Metadata enrichment for Q&A pairs."""

import logging
from datetime import datetime
from typing import Any, Dict

from app.services.document_loaders import RawQAPair

from .keyword_mapper import KeywordMapper

logger = logging.getLogger(__name__)


class MetadataEnricher:
    """Enriches Q&A pairs with metadata."""

    @classmethod
    def enrich(
        cls,
        pair: RawQAPair,
        source_document: str = "",
        existing_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Enrich a Q&A pair with metadata.

        Args:
            pair: Q&A pair to enrich
            source_document: Name of source document
            existing_metadata: Any existing metadata to preserve

        Returns:
            Enriched metadata dictionary
        """
        metadata = existing_metadata.copy() if existing_metadata else {}

        # Preserve existing values if present
        if "category" not in metadata:
            metadata["category"] = KeywordMapper.get_category(pair.question)

        if "intent" not in metadata:
            metadata["intent"] = KeywordMapper.get_intent(pair.question)

        if "requires_handoff" not in metadata:
            metadata["requires_handoff"] = KeywordMapper.get_handoff_required(pair.answer)

        if "confidence_threshold" not in metadata:
            metadata["confidence_threshold"] = KeywordMapper.get_confidence_threshold(pair.answer)

        if "clarifying_questions" not in metadata:
            metadata["clarifying_questions"] = KeywordMapper.generate_clarifying_questions(
                pair.question, pair.answer
            )

        # Add extraction metadata
        metadata["source_document"] = source_document
        metadata["extraction_date"] = datetime.utcnow().isoformat()
        metadata["extraction_method"] = pair.extraction_method
        metadata["confidence_score"] = pair.confidence

        return metadata
