from typing import Optional
from app.observability.langfuse_client import get_langfuse_client

def log_score(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
    observation_id: Optional[str] = None
):
    """
    Log a score to Langfuse.
    """
    client = get_langfuse_client()
    if not client:
        return
        
    client.create_score(
        trace_id=trace_id,
        observation_id=observation_id,
        name=name,
        value=value,
        comment=comment
    )
