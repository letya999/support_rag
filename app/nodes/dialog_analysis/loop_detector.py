"""
Topic Loop Detector for Dialog Analysis.

Detects when a user is stuck in a conversational loop by:
1. Translating all messages to English (for consistent embeddings)
2. Comparing semantic similarity on English text
3. Using high threshold (0.85) for accurate detection
"""
from typing import List, Dict, Any, Optional
import numpy as np
from app.integrations.embeddings_opensource import get_embeddings_batch


async def detect_topic_loop(
    current_question: str,
    conversation_history: List[Any],
    similarity_threshold: float = 0.85,  # Higher threshold for English embeddings
    window_size: int = 4,
    min_messages_for_loop: int = 3,
    translated_query: Optional[str] = None,  # Pre-translated current question
    detected_language: Optional[str] = None   # Current language
) -> Dict[str, Any]:
    """
    Detect if user is stuck in a topic loop using translation-based approach.
    
    Translation-based approach:
    - All questions are translated to English before comparison
    - Embeddings on English text are more reliable and consistent
    - Solves the problem with multilingual-e5-small giving high similarity for different topics in Russian
    
    Args:
        current_question: Current user message (original language)
        conversation_history: Recent conversation history
        similarity_threshold: Cosine similarity threshold (default 0.85 for English)
        window_size: How many recent user messages to check (default 4)
        min_messages_for_loop: Minimum repetitions to consider a loop (default 3)
        translated_query: Pre-translated current question (if available from pipeline)
        detected_language: Detected language of current question
        
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
        
        # ========================================
        # TRANSLATION-BASED APPROACH
        # ========================================
        # Step 1: Translate all messages to English (if not already)
        # This gives us consistent, high-quality embeddings
        
        from app.integrations.translation import translate_text
        
        # Translate current question if not already translated
        if translated_query and detected_language and detected_language != "en":
            current_en = translated_query
            print(f"[LoopDetector] Using pre-translated query: '{current_question}' -> '{current_en}'")
        elif detected_language == "en":
            current_en = current_question
            print(f"[LoopDetector] Current question already in English")
        else:
            # Fallback: translate now
            current_en = await translate_text(current_question, target_lang="en")
            print(f"[LoopDetector] Translated current: '{current_question}' -> '{current_en}'")
        
        # Translate history messages
        # OPTIMIZATION: Use pre-saved translations from message metadata
        translated_history = []
        for msg in user_messages:
            # Try to get pre-translated version from metadata (saved by archive_session)
            if isinstance(msg, dict):
                # Check metadata first
                if "translated" in msg.get("metadata", {}):
                    translated_history.append(msg["metadata"]["translated"])
                elif "translated" in msg:  # Direct field
                    translated_history.append(msg["translated"])
                else:
                    # Fallback: translate now (only if not cached)
                    msg_text = msg.get("content", "")
                    translated = await translate_text(msg_text, target_lang="en")
                    translated_history.append(translated)
            else:
                # String message - translate now
                translated = await translate_text(msg, target_lang="en")
                translated_history.append(translated)
        
        print(f"[LoopDetector] Using {len([h for h in translated_history if h])} pre-translated messages from cache")
        
        all_english_messages = [current_en] + translated_history
        print(f"[LoopDetector] Comparing {len(all_english_messages)} English messages")
        
        # Step 2: Get embeddings for English text
        embeddings = await get_embeddings_batch(all_english_messages[:window_size])
        
        # Step 3: Calculate similarities
        current_embedding = np.array(embeddings[0])
        similarities = []
        similar_indices = []
        
        for idx, other_embedding in enumerate(embeddings[1:]):
            other_embedding = np.array(other_embedding)
            similarity = np.dot(current_embedding, other_embedding) / (
                np.linalg.norm(current_embedding) * np.linalg.norm(other_embedding)
            )
            similarities.append(float(similarity))
            
            if similarity >= similarity_threshold:
                similar_indices.append(idx + 1)
        
        print(f"[LoopDetector] Similarities (English): {[f'{s:.3f}' for s in similarities]}")
        print(f"[LoopDetector] Similar messages (>={similarity_threshold}): {len(similar_indices)}")
        
        # Step 4: Detect loop
        loop_detected = len(similar_indices) >= (min_messages_for_loop - 1)
        average_similarity = np.mean(similarities) if similarities else 0.0
        
        print(f"[LoopDetector] Final decision: loop_detected={loop_detected}")

        
        # Calculate confidence
        if loop_detected:
            count_factor = min(len(similar_indices) / window_size, 1.0)
            similarity_factor = min(average_similarity, 1.0)
            loop_confidence = (count_factor + similarity_factor) / 2.0
        else:
            loop_confidence = average_similarity
        
        return {
            "topic_loop_detected": loop_detected,
            "loop_confidence": float(loop_confidence),
            "similar_messages_count": len(similar_indices),
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
