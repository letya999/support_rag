from langchain_openai import ChatOpenAI
from app.settings import settings

def get_llm(model: str = "gpt-4o-mini", temperature: float = 0, json_mode: bool = False):
    """
    Get configured LLM client.
    """
    kwargs = {
        "model": model,
        "temperature": temperature,
        "api_key": settings.OPENAI_API_KEY
    }
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        
    return ChatOpenAI(**kwargs)
