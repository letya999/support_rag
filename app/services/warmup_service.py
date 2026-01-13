"""
Model Warmup Service.

Handles warming up ML models on application startup to prevent
first-request latency.
"""
import asyncio
from app.integrations.embeddings import get_embedding
from app.logging_config import logger


class WarmupService:
    """Service for warming up models on startup."""
    
    @staticmethod
    async def warmup_all():
        """
        Warm up all models used in the pipeline.
        
        This prevents the first user from experiencing 10+ second delays
        by pre-loading all models during startup.
        """
        loop = asyncio.get_running_loop()
        
        try:
            # 1. Reranker
            from app.nodes.reranking.ranker import get_reranker
            ranker = get_reranker()
            await loop.run_in_executor(None, ranker.rank, "warmup", ["warmup"])
            logger.info("Reranker Warmed Up")
            
            # 2. Classifier (Semantic - Multilingual)
            from app.services.classification.semantic_service import SemanticClassificationService
            svc = SemanticClassificationService()
            # Force model load and first inference (to load weights to GPU/CPU)
            await svc._ensure_model()
            # Run dummy classification to finalize initialization
            await svc.classify("warmup check")
            logger.info("Classifier Warmed Up (Multilingual)")

            # 3. Embeddings
            await get_embedding("warmup")
            logger.info("Embeddings Warmed Up")

            # 4. Translator
            from app.services.translation.translator import translator
            await loop.run_in_executor(None, translator.warmup)
            logger.info("Translator Warmed Up")

            # 5. Guardrails
            from app.nodes.input_guardrails.node import input_guardrails_node
            await input_guardrails_node.warmup()
            logger.info("Guardrails Warmed Up")

        except Exception as e:
            logger.error("Warmup failed", extra={"error": str(e)})
    
    @staticmethod
    async def warmup_embeddings_only():
        """Warm up only embeddings (fast warmup)."""
        try:
            await get_embedding("warmup")
            logger.info("Embeddings Warmed Up (partial)")
        except Exception as e:
            logger.error("Embeddings warmup failed", extra={"error": str(e)})
