from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class ConversationConfig(BaseSettings):
    # Aggregation
    aggregation_max_messages: int = 6
    extract_entities_enabled: bool = True
    use_llm_aggregation: bool = False  # for A/B testing
    use_llm_analysis: bool = True  # LLM-based dialog analysis

    # Session management
    session_ttl_hours: int = 24
    session_timeout_minutes: int = 30
    session_idle_threshold_minutes: int = 5

    # Escalation logic
    max_attempts_before_escalation: int = 3
    escalation_confidence_threshold: float = 0.5
    sentiment_escalation_threshold: float = 0.8

    # Clarification
    clarification_enabled: bool = True
    clarification_confidence_range: List[float] = [0.3, 0.6]

    # Response
    max_response_tokens: int = 500

    # Persistence
    persist_to_postgres: bool = True
    summarize_on_escalation: bool = True

    # Category/Intent routing
    always_escalate_categories: List[str] = ["billing_dispute", "account_closure", "complaint"]
    always_escalate_intents: List[str] = ["urgent", "vip"]
    
    model_config = SettingsConfigDict(
        env_prefix="CONV_",
        env_file=".env",
        extra="ignore"
    )

conversation_config = ConversationConfig()
