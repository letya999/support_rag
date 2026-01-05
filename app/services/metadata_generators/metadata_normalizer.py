"""Metadata normalization and validation."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MetadataNormalizer:
    """Normalizes and validates metadata."""

    VALID_CATEGORIES = {
        "Account Access",
        "Order Management",
        "Payment & Billing",
        "Account Management",
        "Support",
        "Technical",
        "Features & Usage",
        "General",
    }

    VALID_INTENTS = {
        "how_to",
        "provide_info",
        "check_capability",
        "locate_resource",
        "troubleshoot",
        "account_action",
        "contact_support",
        "general",
    }

    @classmethod
    def normalize(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate metadata.

        Args:
            metadata: Metadata dict to normalize

        Returns:
            Normalized metadata dict
        """
        normalized = {}

        # Normalize category
        category = metadata.get("category", "General")
        if category not in cls.VALID_CATEGORIES:
            logger.warning(f"Invalid category '{category}', using 'General'")
            category = "General"
        normalized["category"] = category

        # Normalize intent
        intent = metadata.get("intent", "provide_info")
        if intent not in cls.VALID_INTENTS:
            logger.warning(f"Invalid intent '{intent}', using 'provide_info'")
            intent = "provide_info"
        normalized["intent"] = intent

        # Normalize boolean fields
        normalized["requires_handoff"] = bool(metadata.get("requires_handoff", False))

        # Normalize confidence threshold
        conf_threshold = metadata.get("confidence_threshold", 0.8)
        try:
            conf_threshold = float(conf_threshold)
            conf_threshold = max(0.0, min(1.0, conf_threshold))
        except (ValueError, TypeError):
            logger.warning(f"Invalid confidence_threshold, using 0.8")
            conf_threshold = 0.8
        normalized["confidence_threshold"] = conf_threshold

        # Normalize clarifying questions
        clarifying_questions = metadata.get("clarifying_questions", [])
        if not isinstance(clarifying_questions, list):
            clarifying_questions = [clarifying_questions] if clarifying_questions else []
        clarifying_questions = [str(q).strip() for q in clarifying_questions if q]
        normalized["clarifying_questions"] = clarifying_questions

        # Preserve other fields
        for key in ["source_document", "extraction_date", "extraction_method", "confidence_score"]:
            if key in metadata:
                normalized[key] = metadata[key]

        return normalized

    @classmethod
    def validate(cls, metadata: Dict[str, Any]) -> tuple:
        """Validate metadata.

        Args:
            metadata: Metadata to validate

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check required fields
        if "category" not in metadata:
            errors.append("Missing 'category' field")
        elif metadata["category"] not in cls.VALID_CATEGORIES:
            errors.append(f"Invalid category: {metadata['category']}")

        if "intent" not in metadata:
            errors.append("Missing 'intent' field")
        elif metadata["intent"] not in cls.VALID_INTENTS:
            errors.append(f"Invalid intent: {metadata['intent']}")

        # Check data types
        if "requires_handoff" in metadata:
            if not isinstance(metadata["requires_handoff"], bool):
                errors.append("'requires_handoff' must be boolean")

        if "confidence_threshold" in metadata:
            try:
                val = float(metadata["confidence_threshold"])
                if not 0.0 <= val <= 1.0:
                    errors.append("'confidence_threshold' must be between 0 and 1")
            except (ValueError, TypeError):
                errors.append("'confidence_threshold' must be a number")

        if "clarifying_questions" in metadata:
            if not isinstance(metadata["clarifying_questions"], list):
                errors.append("'clarifying_questions' must be a list")

        return len(errors) == 0, errors
