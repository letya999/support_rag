"""
Conversation configuration wrapper.
Integrates with the centralized YAML configuration loader.
Reads from pipeline_config.yaml.
"""
from typing import List
from app.services.config_loader.loader import get_node_params, get_global_param, get_node_enabled

class ConversationConfig:
    @property
    def aggregation_max_messages(self) -> int:
        return get_node_params("aggregation").get("history_messages_count", 6)

    @property
    def use_llm_aggregation(self) -> bool:
        return get_node_enabled("aggregation") and get_node_params("aggregation").get("mode") == "llm"

    @property
    def use_llm_analysis(self) -> bool:
        return get_node_params("dialog_analysis").get("mode") == "llm"

    @property
    def session_ttl_hours(self) -> int:
        return get_global_param("session_ttl_hours", 24)

    @property
    def session_timeout_minutes(self) -> int:
        return get_global_param("session_timeout_minutes", 30)

    @property
    def conversation_cache_ttl_seconds(self) -> int:
        """
        TTL for Redis conversation history cache (hot storage).
        Returns: Seconds (default: 1800 = 30 minutes)
        """
        ttl_minutes = get_global_param("conversation_cache_ttl_minutes", None)
        if ttl_minutes is not None:
            return ttl_minutes * 60
        
        # Fallback: use 1/24 of session_ttl (if 24h, then 1h)
        session_ttl_hours = get_global_param("session_ttl_hours", 24)
        return int(session_ttl_hours * 3600 / 24)

    @property
    def session_idle_threshold_minutes(self) -> int:
        return get_global_param("session_idle_threshold_minutes", 5)

    @property
    def max_attempts_before_escalation(self) -> int:
        return get_node_params("state_machine").get("max_attempts_before_handoff", 3)

    @property
    def escalation_confidence_threshold(self) -> float:
        return get_node_params("routing").get("min_confidence_auto_reply", 0.5)

    @property
    def clarification_enabled(self) -> bool:
        return get_node_params("routing").get("clarification_enabled", True)

    @property
    def clarification_confidence_range(self) -> List[float]:
        return get_node_params("routing").get("clarification_confidence_range", [0.3, 0.6])

    @property
    def persist_to_postgres(self) -> bool:
        return get_global_param("persist_to_postgres", True)

    @property
    def always_escalate_categories(self) -> List[str]:
        return get_node_params("routing").get("always_escalate_categories", [])

    @property
    def always_escalate_intents(self) -> List[str]:
        return get_node_params("routing").get("always_escalate_intents", [])

    @property
    def max_response_tokens(self) -> int:
        return get_node_params("generation").get("max_tokens", 500)

# Singleton instance
conversation_config = ConversationConfig()
