"""
History filtering utilities.

Filters system messages and noise from conversation history
based on patterns defined in system_phrases.yaml.
"""
import re
from typing import List, Dict, Any, Optional
from functools import lru_cache
from app.services.config_loader.loader import load_shared_config


@lru_cache(maxsize=1)
def _load_filter_patterns() -> List[Dict[str, str]]:
    """
    Load filter patterns from system_phrases.yaml.
    Returns empty list if config not found.
    """
    try:
        config = load_shared_config("system_phrases")
        return config.get("filter_patterns", [])
    except Exception:
        # Fallback patterns if config not available
        return [
            {"regex": "Извините, не смог обработать", "type": "error"},
            {"regex": "Произошла ошибка", "type": "error"},
            {"regex": "Соединяю с оператором", "type": "handoff"},
            {"regex": "Sorry, couldn't process", "type": "error"},
            {"regex": "Connecting you to", "type": "handoff"},
        ]


def is_system_message(content: str) -> bool:
    """
    Check if a message matches any system phrase pattern.
    
    Args:
        content: Message content to check
        
    Returns:
        True if message is a system message (should be filtered)
    """
    if not content:
        return False
    
    patterns = _load_filter_patterns()
    for pattern in patterns:
        regex = pattern.get("regex", "")
        if regex and re.search(regex, content, re.IGNORECASE):
            return True
    return False


def filter_conversation_history(
    history: List[Dict[str, Any]],
    max_messages: Optional[int] = None,
    include_assistant: bool = True
) -> List[Dict[str, Any]]:
    """
    Filter conversation history, removing system messages.
    
    Args:
        history: List of messages with {role, content} format
        max_messages: Maximum number of messages to return (None = all)
        include_assistant: Whether to include assistant messages
        
    Returns:
        Filtered list of messages
    """
    if not history:
        return []
    
    filtered = []
    for msg in history:
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
        
        # Skip assistant messages if not included
        if not include_assistant and role == "assistant":
            continue
        
        # Skip system messages based on patterns
        if role == "assistant" and is_system_message(content):
            continue
        
        # Skip very short messages (likely noise)
        if len(content.strip()) < 2:
            continue
        
        filtered.append(msg)
    
    # Apply max limit
    if max_messages and len(filtered) > max_messages:
        filtered = filtered[-max_messages:]
    
    return filtered


def filter_session_history(
    sessions: List[Dict[str, Any]],
    max_sessions: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Filter session history, removing sessions with system-only content.
    
    Args:
        sessions: List of sessions with {session_id, outcome, summary}
        max_sessions: Maximum number of sessions to return
        
    Returns:
        Filtered list of sessions
    """
    if not sessions:
        return []
    
    filtered = []
    for session in sessions:
        summary = session.get("summary", "")
        
        # Skip if summary is a system message
        if summary and is_system_message(summary):
            continue
        
        # Skip empty summaries
        if not summary or len(summary.strip()) < 5:
            continue
        
        filtered.append(session)
    
    # Apply max limit
    if max_sessions and len(filtered) > max_sessions:
        filtered = filtered[-max_sessions:]
    
    return filtered


def get_clean_history_for_prompt(
    state: Dict[str, Any],
    max_messages: int = 5
) -> List[Dict[str, Any]]:
    """
    Get clean conversation history suitable for prompt building.
    
    Tries conversation_history first, falls back to session_history summaries.
    
    Args:
        state: Pipeline state
        max_messages: Maximum messages to return
        
    Returns:
        List of {role, content} messages
    """
    # 1. Try conversation_history (proper format)
    conv_history = state.get("conversation_history", [])
    if conv_history:
        return filter_conversation_history(
            conv_history,
            max_messages=max_messages,
            include_assistant=True
        )
    
    # 2. Fallback to session_history summaries
    session_history = state.get("session_history", [])
    if session_history:
        filtered_sessions = filter_session_history(session_history, max_sessions=3)
        # Convert to message format
        messages = []
        for session in filtered_sessions:
            summary = session.get("summary", "")
            if summary:
                messages.append({
                    "role": "system",
                    "content": f"[Предыдущий разговор] {summary}"
                })
        return messages
    
    return []


def clear_filter_cache():
    """Clear cached filter patterns for hot reload."""
    _load_filter_patterns.cache_clear()
