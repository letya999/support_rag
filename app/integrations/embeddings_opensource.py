import asyncio
from typing import List, Union
from sentence_transformers import SentenceTransformer
import torch
from langfuse import observe
from concurrent.futures import ThreadPoolExecutor

# Create a dedicated executor for embeddings to avoid blocking the main loop
# and limit the number of parallel threads if needed (though 1 is often enough for model inference)
executor = ThreadPoolExecutor(max_workers=1)

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

async def _get_embedding_base(text: str) -> List[float]:
    """Base logic for getting a single embedding."""
    loop = asyncio.get_running_loop()
    # Run in executor to avoid blocking event loop
    embeddings = await loop.run_in_executor(
        executor, 
        embedding_model.encode_sync, 
        [f"query: {text}"], 
        1
    )
    return embeddings[0]

@observe(as_type="span", name="get_embedding")
async def _get_embedding_observed(text: str) -> List[float]:
    """Observed version of get_embedding."""
    return await _get_embedding_base(text)

async def get_embedding(text: str) -> List[float]:
    """
    Get embedding for a single string (Query).
    Adds 'query: ' prefix as required by E5 models.
    Skips Langfuse if text is 'warmup'.
    """
    if text == "warmup":
        return await _get_embedding_base(text)
    return await _get_embedding_observed(text)

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

@observe(as_type="span", name="get_embeddings_batch")
async def _get_embeddings_batch_observed(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Observed version of get_embeddings_batch."""
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
