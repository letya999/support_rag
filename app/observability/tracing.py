from typing import Optional

try:
    from langfuse.decorators import observe, langfuse_context
except ImportError:
    from langfuse import observe
    langfuse_context = None

# Re-export observe decorator and context
__all__ = ["observe", "langfuse_context"]
