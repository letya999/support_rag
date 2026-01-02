"""Models for metadata filtering."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class FilteringOutput(BaseModel):
    """Output from metadata filtering."""

    docs: List[str] = Field(
        ...,
        description="Retrieved documents (filtered or full search)"
    )
    docs_with_metadata: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Documents with metadata and scores"
    )
    filter_used: bool = Field(
        ...,
        description="Was category filtering applied?"
    )
    fallback_triggered: bool = Field(
        ...,
        description="Did we fallback to full search due to low results?"
    )
    reason: str = Field(
        ...,
        description="Explanation for filtering decision"
    )
    category_docs_count: Optional[int] = Field(
        None,
        description="Number of documents in filtered category (if used)"
    )
    total_docs_searched: int = Field(
        ...,
        description="Total documents searched"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "docs": ["Doc 1 content", "Doc 2 content"],
                "filter_used": True,
                "fallback_triggered": False,
                "reason": "Filtered by shipping - found 2 docs",
                "category_docs_count": 5,
                "total_docs_searched": 2
            }
        }
