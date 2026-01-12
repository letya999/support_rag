import asyncio
from typing import List, Union
from sentence_transformers import SentenceTransformer
import torch
import torch
from app.observability.tracing import langfuse_context, observe
from concurrent.futures import ThreadPoolExecutor

import os

# Create a dedicated executor for embeddings to avoid blocking the main loop
# Using more workers to allow parallel inference (torch releases GIL)
executor = ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) * 4))

class EmbeddingModel:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading embedding model {model_name} on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.vector_size = self.model.get_sentence_embedding_dimension()

    def encode_sync(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        import time
        start = time.perf_counter()
        
        # Clean newlines as recommended
        clean_texts = [t.replace("\n", " ") for t in texts]
        embeddings = self.model.encode(clean_texts, batch_size=batch_size, normalize_embeddings=True)
        
        duration_ms = (time.perf_counter() - start) * 1000
        print(f"[Embeddings] Encoded {len(texts)} texts in {duration_ms:.2f}ms")
        
        return embeddings.tolist()

# Initialize global instance
embedding_model = EmbeddingModel.get_instance()

async def _get_embedding_base(text: str, is_query: bool = True) -> List[float]:
    """Base logic for getting a single embedding."""
    loop = asyncio.get_running_loop()
    prefix = "query: " if is_query else "passage: "
    # Run in executor to avoid blocking event loop
    embeddings = await loop.run_in_executor(
        executor, 
        embedding_model.encode_sync, 
        [f"{prefix}{text}"], 
        1
    )
    return embeddings[0]

# Removed @observe to prevent logging full vector
async def _get_embedding_observed(text: str, is_query: bool = True) -> List[float]:
    """Observed version of get_embedding."""
    # Manual tracing to avoid logging full vector
    # Check if langfuse_context is available and active
    if langfuse_context and langfuse_context.get_current_trace_id():
        span = langfuse_context.span(
            name="get_embedding",
            input={"text": text, "is_query": is_query}
        )
        try:
            result = await _get_embedding_base(text, is_query)
            if span:
                span.end(output={"vector_size": len(result), "sample": result[:5]})
            return result
        except Exception as e:
            if span:
                span.end(level="ERROR", status_message=str(e))
            raise
    else:
        return await _get_embedding_base(text, is_query)

async def get_embedding(text: str, is_query: bool = True) -> List[float]:
    """
    Get embedding for a single string.
    Adds 'query: ' prefix for queries and 'passage: ' for documents.
    Skips Langfuse if text is 'warmup'.
    """
    if text == "warmup":
        return await _get_embedding_base(text, is_query)
    return await _get_embedding_observed(text, is_query)

async def _get_embeddings_batch_base(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Base logic for getting batch embeddings."""
    if not texts:
        return []
    
    # Add prefix
    prefixed_texts = [f"passage: {t}" for t in texts]
        
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(
        executor,
        embedding_model.encode_sync,
        prefixed_texts,
        batch_size
    )
    return embeddings

# Removed @observe to prevent logging full vector
async def _get_embeddings_batch_observed(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Observed version of get_embeddings_batch."""
    # Check if langfuse_context is available and active
    if langfuse_context and langfuse_context.get_current_trace_id():
        span = langfuse_context.span(
            name="get_embeddings_batch",
            input={"count": len(texts), "batch_size": batch_size}
        )
        try:
            results = await _get_embeddings_batch_base(texts, batch_size)
            if span:
                span.end(output={"count": len(results), "vector_size": len(results[0]) if results else 0})
            return results
        except Exception as e:
            if span:
                span.end(level="ERROR", status_message=str(e))
            raise
    else:
        return await _get_embeddings_batch_base(texts, batch_size)

async def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Get embeddings for a list of strings (Passages).
    Adds 'passage: ' prefix as required by E5 models.
    Skips Langfuse if first text is 'warmup'.
    """
    if texts and texts[0] == "warmup":
        return await _get_embeddings_batch_base(texts, batch_size)
    return await _get_embeddings_batch_observed(texts, batch_size)
