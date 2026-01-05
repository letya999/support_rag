from typing import List
from app.integrations.embeddings_opensource import get_embedding as get_os_embedding

async def get_embedding(text: str, model: str = "all-MiniLM-L6-v2", is_query: bool = True) -> List[float]:
    """
    Get embedding for text using Open Source model.
    Model param is kept for compatibility but currently ignored/defaulted to MiniLM.
    is_query: determines if 'query:' or 'passage:' prefix is used (for E5).
    """
    return await get_os_embedding(text, is_query=is_query)
