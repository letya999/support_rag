"""
Topic Loop Detector for Dialog Analysis.

Detects when a user is stuck in a conversational loop by:
1. Checking semantic similarity of recent user messages
2. Identifying repeated topics even with different wording
"""
from typing import List, Dict, Any, Optional
import numpy as np
from app.integrations.embeddings_opensource import get_embeddings_batch


async def detect_topic_loop(
    current_question: str,
    conversation_history: List[Any],
    similarity_threshold: float = 0.8,
    window_size: int = 4,
    min_messages_for_loop: int = 3
) -> Dict[str, Any]:
    """
    Detect if user is stuck in a topic loop.
    
    Args:
        current_question: Current user message
        conversation_history: Recent conversation history
        similarity_threshold: Cosine similarity threshold (default 0.8)
        window_size: How many recent user messages to check (default 4)
        min_messages_for_loop: Minimum repetitions to consider a loop (default 3)
        
    Returns:
        Dict with:
        - topic_loop_detected: bool
        - loop_confidence: float (0.0-1.0)
        - similar_messages_count: int
        - average_similarity: float
    """
    try:
        # Extract recent user messages from history
        user_messages = []
        for msg in reversed(conversation_history):
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content", "")
            else:
                # Handle LangChain message objects
                role = getattr(msg, "type", "unknown")
                content = getattr(msg, "content", "")
            
            if role in ["user", "human"]:
                user_messages.append(content)
                if len(user_messages) >= window_size:
                    break
        
        # Need at least min_messages_for_loop to detect a loop
        if len(user_messages) < min_messages_for_loop - 1:
            return {
                "topic_loop_detected": False,
                "loop_confidence": 0.0,
                "similar_messages_count": 0,
                "average_similarity": 0.0
            }
        
        # Add current question to the front
        all_user_messages = [current_question] + user_messages
        
        # Get embeddings for all user messages (batch)
        embeddings = await get_embeddings_batch(all_user_messages[:window_size])
        
        # Calculate pairwise cosine similarities
        current_embedding = np.array(embeddings[0])
        similarities = []
        
        for other_embedding in embeddings[1:]:
            other_embedding = np.array(other_embedding)
            # Cosine similarity
            similarity = np.dot(current_embedding, other_embedding) / (
                np.linalg.norm(current_embedding) * np.linalg.norm(other_embedding)
            )
            similarities.append(float(similarity))
        
        # Count high-similarity messages
        high_similarity_count = sum(1 for sim in similarities if sim >= similarity_threshold)
        average_similarity = np.mean(similarities) if similarities else 0.0
        
        # Loop detected if we have enough similar messages
        loop_detected = high_similarity_count >= (min_messages_for_loop - 1)
        
        # Calculate confidence based on average similarity and count
        if loop_detected:
            # Confidence increases with both count and similarity
            count_factor = min(high_similarity_count / window_size, 1.0)
            similarity_factor = min(average_similarity, 1.0)
            loop_confidence = (count_factor + similarity_factor) / 2.0
        else:
            loop_confidence = average_similarity  # Even if not loop, show how close we are
        
        return {
            "topic_loop_detected": loop_detected,
            "loop_confidence": float(loop_confidence),
            "similar_messages_count": high_similarity_count,
            "average_similarity": float(average_similarity)
        }
        
    except Exception as e:
        print(f"⚠️ Loop detection failed: {e}")
        # Fail gracefully - don't block the pipeline
        return {
            "topic_loop_detected": False,
            "loop_confidence": 0.0,
            "similar_messages_count": 0,
            "average_similarity": 0.0,
            "error": str(e)
        }
