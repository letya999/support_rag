from typing import List
from app.integrations.embeddings_opensource import get_embedding as get_os_embedding

async def get_embedding(text: str, model: str = "all-MiniLM-L6-v2") -> List[float]:
    """
    Get embedding for text using Open Source model.
    Model param is kept for compatibility but currently ignored/defaulted to MiniLM.
    """
    return await get_os_embedding(text)
