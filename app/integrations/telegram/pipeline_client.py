"""
RAG Pipeline Client

HTTP client for communicating with the RAG pipeline API.
"""

import aiohttp
import logging
from typing import List, Optional, Dict, Any

from app.integrations.telegram.models import RAGRequest, RAGResponse

logger = logging.getLogger(__name__)


class RAGPipelineClient:
    """
    HTTP client for RAG pipeline.

    Communicates with the main RAG API to process user queries with conversation context.
    """

    def __init__(self, api_url: str):
        """
        Initialize RAG pipeline client.

        Args:
            api_url: Base URL of RAG API (e.g., "http://api:8000")
        """
        self.api_url = api_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Initialize HTTP session"""
        try:
            self.session = aiohttp.ClientSession()
            logger.info(f"RAG client initialized for {self.api_url}")
        except Exception as e:
            logger.error(f"Failed to initialize RAG client: {e}")
            raise

    async def disconnect(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            logger.info("RAG client disconnected")

    async def query_rag(
        self,
        question: str,
        conversation_history: List[dict],
        user_id: int,
        session_id: str,
        user_metadata: Dict[str, Any] = {}
    ) -> RAGResponse:
        """
        Query RAG pipeline with question and conversation context.

        Args:
            question: User's question
            conversation_history: Previous messages for context [{"role": "user/assistant", "content": "..."}, ...]
            user_id: Telegram user ID
            session_id: Session identifier
            user_metadata: Extra user info (username, language, etc.)

        Returns:
            RAGResponse with answer, sources, and confidence
        """

        request = RAGRequest(
            question=question,
            conversation_history=conversation_history,
            user_id=str(user_id),
            session_id=session_id,
            user_metadata=user_metadata
        )

        try:
            logger.debug(f"Querying RAG for user {user_id}: {question[:50]}...")

            async with self.session.post(
                f"{self.api_url}/api/v1/chat/completions",
                json=request.model_dump(),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"RAG API error {response.status}: {error_text[:200]}"
                    )
                    # Return fallback response on error
                    return RAGResponse(
                        answer="Извините, не смог обработать ваш вопрос. Попробуйте позже.",
                        sources=[],
                        confidence=0.0,
                        query_id="error"
                    )

                payload = await response.json()
                data = payload.get("data", {})
                
                # Map API response fields to RAGResponse model
                sources_data = []
                for src in data.get("sources", []):
                    sources_data.append({
                        "title": src.get("title", "Document"),
                        "doc_id": src.get("document_id", ""),
                        "relevance": src.get("relevance", 0.0),
                        "metadata": src.get("metadata", {})
                    })

                rag_response_data = {
                    "answer": data.get("answer", ""),
                    "sources": sources_data,
                    "confidence": data.get("confidence", 0.0),
                    "query_id": data.get("query_id", ""),
                    "metadata": data.get("pipeline_metadata", {})
                }

                logger.debug(f"RAG response received for user {user_id}")
                return RAGResponse(**rag_response_data)

        except aiohttp.ClientError as e:
            logger.error(f"RAG API connection error: {e}")
            return RAGResponse(
                answer="Ошибка подключения к сервису. Попробуйте позже.",
                sources=[],
                confidence=0.0,
                query_id="connection_error"
            )
        except Exception as e:
            logger.error(f"Unexpected error querying RAG: {e}", exc_info=True)
            return RAGResponse(
                answer="Произошла неожиданная ошибка. Попробуйте позже.",
                sources=[],
                confidence=0.0,
                query_id="unexpected_error"
            )
