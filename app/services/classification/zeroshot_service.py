import logging
from typing import List, Dict, Any
from pydantic import BaseModel
import numpy as np

from app.services.classification.semantic_service import SemanticClassificationService

logger = logging.getLogger(__name__)


class CategoryIntent(BaseModel):
    """Represents a category with its intents."""
    name: str
    intents: List[str]


class ZeroShotResult(BaseModel):
    """Result of zero-shot classification."""
    chunk_id: str
    intent: str
    category: str
    confidence: float


class ZeroShotClassificationService:
    """
    Zero-shot classification service that classifies chunks against 
    a predefined taxonomy (categories and intents) WITHOUT using LLM 
    to name clusters. Uses semantic similarity to match chunks to intents.
    """
    
    def __init__(self):
        self.semantic_service = SemanticClassificationService()
    
    async def classify_chunks(
        self, 
        chunks: List[Dict[str, Any]], 
        taxonomy: List[CategoryIntent]
    ) -> List[ZeroShotResult]:
        """
        Classify chunks against a predefined taxonomy.
        
        Args:
            chunks: List of chunks with 'chunk_id' and 'question' fields
            taxonomy: List of CategoryIntent objects defining the classification structure
            
        Returns:
            List of ZeroShotResult objects with predicted category, intent, and confidence
        """
        if not chunks or not taxonomy:
            logger.warning("Cannot classify: empty chunks or taxonomy")
            return []
        
        # Filter valid chunks
        valid_chunks = [c for c in chunks if c.get("question")]
        if not valid_chunks:
            logger.warning("No valid chunks with questions found")
            return []
        
        # Prepare texts and IDs
        chunk_texts = [c["question"] for c in valid_chunks]
        chunk_ids = [c["chunk_id"] for c in valid_chunks]
        
        # Build flat list of (category, intent) pairs
        intent_labels = []  # List of (category_name, intent_name) tuples
        intent_texts = []   # List of intent names to embed
        
        for cat in taxonomy:
            for intent in cat.intents:
                intent_labels.append((cat.name, intent))
                intent_texts.append(intent)
        
        if not intent_texts:
            logger.warning("No intents found in taxonomy")
            return []
        
        logger.info(f"Classifying {len(chunk_texts)} chunks against {len(intent_texts)} intents...")
        
        # Encode all chunks and all intents
        chunk_embeddings = await self.semantic_service.encode_batch(chunk_texts)
        intent_embeddings = await self.semantic_service.encode_batch(intent_texts)
        
        if chunk_embeddings is None or len(chunk_embeddings) == 0 or intent_embeddings is None or len(intent_embeddings) == 0:
            logger.error("Failed to generate embeddings")
            return []
        
        # Convert to numpy arrays
        chunk_emb_array = np.array(chunk_embeddings)
        intent_emb_array = np.array(intent_embeddings)
        
        # Compute cosine similarity (or use semantic_service methods)
        # Cosine similarity = dot product of normalized vectors
        # Normalize embeddings
        chunk_norms = np.linalg.norm(chunk_emb_array, axis=1, keepdims=True)
        intent_norms = np.linalg.norm(intent_emb_array, axis=1, keepdims=True)
        
        chunk_normalized = chunk_emb_array / (chunk_norms + 1e-9)
        intent_normalized = intent_emb_array / (intent_norms + 1e-9)
        
        # Similarity matrix: [n_chunks, n_intents]
        similarity_matrix = np.dot(chunk_normalized, intent_normalized.T)
        
        # For each chunk, find the best matching intent
        results = []
        for i, chunk_id in enumerate(chunk_ids):
            similarities = similarity_matrix[i]
            best_idx = int(np.argmax(similarities))
            best_score = float(similarities[best_idx])
            
            category_name, intent_name = intent_labels[best_idx]
            
            results.append(ZeroShotResult(
                chunk_id=chunk_id,
                category=category_name,
                intent=intent_name,
                confidence=best_score
            ))
        
        logger.info(f"Successfully classified {len(results)} chunks")
        return results
