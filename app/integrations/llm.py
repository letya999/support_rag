from langchain_openai import ChatOpenAI
from app.config.settings import settings

def get_llm(model: str = "gpt-4o-mini", temperature: float = 0):
    """
    Get configured LLM client.
    """
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY
    )
