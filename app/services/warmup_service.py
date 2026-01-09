"""
Model Warmup Service.

Handles warming up ML models on application startup to prevent
first-request latency.
"""
import asyncio
from app.integrations.embeddings import get_embedding


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
            print("✅ Reranker Warmed Up")
            
            # 2. Classifier
            from app.services.classification.semantic_service import SemanticClassificationService
            svc = SemanticClassificationService()
            await svc._ensure_model()
            print("✅ Classifier Warmed Up")

            # 3. Embeddings
            await get_embedding("warmup")
            print("✅ Embeddings Warmed Up")

            # 4. Translator
            from app.services.translation.translator import translator
            await loop.run_in_executor(None, translator.warmup)
            print("✅ Translator Warmed Up")

            # 5. Guardrails
            from app.nodes.input_guardrails.node import input_guardrails_node
            await input_guardrails_node.warmup()
            print("✅ Guardrails Warmed Up")

        except Exception as e:
            print(f"⚠️ Warmup failed: {e}")
    
    @staticmethod
    async def warmup_embeddings_only():
        """Warm up only embeddings (fast warmup)."""
        try:
            await get_embedding("warmup")
            print("✅ Embeddings Warmed Up")
        except Exception as e:
            print(f"⚠️ Embeddings warmup failed: {e}")
