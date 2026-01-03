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

@observe(as_type="span")
async def get_embedding(text: str) -> List[float]:
    """
    Get embedding for a single string (Query).
    Adds 'query: ' prefix as required by E5 models.
    """
    loop = asyncio.get_running_loop()
    # Run in executor to avoid blocking event loop
    embeddings = await loop.run_in_executor(
        executor, 
        embedding_model.encode_sync, 
        [f"query: {text}"], 
        1
    )
    return embeddings[0]

@observe(as_type="span")
async def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Get embeddings for a list of strings (Passages).
    Adds 'passage: ' prefix as required by E5 models.
    """
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
