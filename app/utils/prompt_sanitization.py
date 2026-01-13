"""
Prompt Sanitization Utilities

Provides functions to sanitize user input before using it in LLM prompts
to prevent prompt injection attacks.
"""

import re
from typing import Any, Dict, List


def sanitize_for_prompt(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user input to prevent prompt injection attacks.

    This function applies multiple layers of defense:
    1. Length limiting to prevent excessive token usage
    2. Removes/escapes common prompt injection patterns
    3. Normalizes whitespace and control characters

    Args:
        text: The user input to sanitize
        max_length: Maximum allowed length (default: 10000 chars)

    Returns:
        Sanitized text safe for use in prompts
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Enforce length limit
    text = text[:max_length]

    # 2. Remove null bytes and other control characters (except newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)

    # 3. Normalize excessive whitespace (but preserve intentional formatting)
    # Replace multiple consecutive newlines with max 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Replace multiple consecutive spaces with single space
    text = re.sub(r' {2,}', ' ', text)

    # 4. Detect and neutralize common prompt injection patterns
    # These patterns attempt to override system instructions
    injection_patterns = [
        # Direct instruction overrides
        (r'(?i)(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions|directives|commands|prompts)',
         r'[USER INPUT: \g<0>]'),

        # Role manipulation attempts
        (r'(?i)(you\s+are\s+now|act\s+as|pretend\s+to\s+be|assume\s+the\s+role)\s+(a\s+)?(\w+)',
         r'[USER INPUT: \g<0>]'),

        # System message injection attempts
        (r'(?i)(system|assistant|user):\s*',
         r'[USER INPUT: \g<0>]'),

        # Delimiter injection attempts (trying to break out of context)
        (r'(?i)(---+|===+|\*\*\*+)(\s*system\s*|\s*assistant\s*|\s*instructions?\s*)(---+|===+|\*\*\*+)',
         r'[USER INPUT: \g<0>]'),
    ]

    for pattern, replacement in injection_patterns:
        text = re.sub(pattern, replacement, text)

    # 5. Escape markdown-style code blocks that could be used to inject instructions
    # Replace triple backticks with a safe representation
    text = text.replace('```', '`‎`‎`')  # Using zero-width joiner to break the sequence

    return text.strip()


def sanitize_dict_values(data: Dict[str, Any], max_length: int = 5000) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.

    Useful for sanitizing user profiles, extracted entities, etc.

    Args:
        data: Dictionary with potentially unsafe user data
        max_length: Maximum length for each string value

    Returns:
        Dictionary with sanitized values
    """
    if not isinstance(data, dict):
        return {}

    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_for_prompt(value, max_length)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict_values(value, max_length)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_for_prompt(item, max_length) if isinstance(item, str)
                else sanitize_dict_values(item, max_length) if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            # Non-string, non-dict, non-list values pass through
            sanitized[key] = value

    return sanitized


def sanitize_list(items: List[str], max_length: int = 5000) -> List[str]:
    """
    Sanitize a list of strings.

    Useful for sanitizing document lists, conversation history, etc.

    Args:
        items: List of strings to sanitize
        max_length: Maximum length for each string

    Returns:
        List of sanitized strings
    """
    if not isinstance(items, list):
        return []

    return [
        sanitize_for_prompt(item, max_length) if isinstance(item, str) else str(item)
        for item in items
    ]


def sanitize_conversation_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitize conversation history messages.

    Preserves the structure but sanitizes content fields.

    Args:
        history: List of message dictionaries with 'role' and 'content' fields

    Returns:
        Sanitized conversation history
    """
    if not isinstance(history, list):
        return []

    sanitized_history = []
    for msg in history:
        if not isinstance(msg, dict):
            continue

        sanitized_msg = msg.copy()
        if 'content' in sanitized_msg and isinstance(sanitized_msg['content'], str):
            sanitized_msg['content'] = sanitize_for_prompt(sanitized_msg['content'])

        sanitized_history.append(sanitized_msg)

    return sanitized_history
