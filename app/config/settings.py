import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Support RAG Engine"
    DEBUG: bool = False
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Database
    DATABASE_URL: str
    QDRANT_URL: str = "http://localhost:6333"
    
    # Langfuse
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = "https://cloud.langfuse.com"
    
    # Parameters
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.7
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
