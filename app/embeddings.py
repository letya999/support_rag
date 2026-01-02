import os
from langfuse.openai import OpenAI
from typing import List
from langfuse import observe
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@observe(as_type="span")
async def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")
    # Use the async client if possible, but Langfuse wrapper is often sync-first
    # For now, keeping the call but making the function async to preserve contextvars
    client = OpenAI(api_key=OPENAI_API_KEY)
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding
