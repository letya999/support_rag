"""Pydantic models for classification node."""

from pydantic import BaseModel, Field
from typing import Optional, Dict


class ClassificationOutput(BaseModel):
    """Output from classification node."""

    intent: str = Field(
        ...,
        description="Classified intent (faq, complaint, suggestion, etc)"
    )
    intent_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for intent (0.0-1.0)"
    )
    category: str = Field(
        ...,
        description="Classified category (billing, shipping, account, etc)"
    )
    category_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for category (0.0-1.0)"
    )
    all_category_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="All categories ranked by confidence"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "faq",
                "intent_confidence": 0.95,
                "category": "shipping",
                "category_confidence": 0.87,
                "all_category_scores": {
                    "shipping": 0.87,
                    "returns": 0.08,
                    "product": 0.03,
                    "billing": 0.01,
                    "account": 0.01,
                    "technical": 0.0,
                    "general": 0.0
                }
            }
        }
