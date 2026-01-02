from typing import List
from langfuse.openai import OpenAI
from langfuse import observe
from app.config.settings import settings

@observe(as_type="span")
async def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Get embedding for text using OpenAI.
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")
        
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    text = text.replace("\n", " ")
    
    # Note: langfuse.openai.OpenAI is sync wrapper usually, but let's check if we can make it async or use it as is.
    # The original code had it wrapped in async def but called sync client methods.
    # To keep fully async we might want AsyncOpenAI but Langfuse support for AsyncOpenAI needs check.
    # For now, following original implementation's pattern but acknowledging it might be blocking.
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding
