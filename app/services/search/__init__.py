"""
Search service for API layer.

This module provides unified search interfaces abstracting retrieval operations.
"""
from app.services.search.search_service import search_documents, search_lexical

__all__ = ["search_documents", "search_lexical"]
