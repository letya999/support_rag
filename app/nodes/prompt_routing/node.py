"""
Prompt Routing Node.

Selects and builds the system prompt based on dialog state.
Uses correct conversation_history format instead of session_history.
"""
from typing import Dict, Any, List, Optional
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
try:
    from app.nodes._shared_config.history_filter import get_clean_history_for_prompt, is_system_message
except ImportError:
    get_clean_history_for_prompt = None
    is_system_message = None
from app.services.config_loader.loader import get_node_params

# Default config values
DEFAULT_MAX_HISTORY_MESSAGES = 5
DEFAULT_MAX_MESSAGE_LENGTH = 300

def _get_params() -> Dict[str, Any]:
    """Get node parameters and config from centralized config."""
    try:
        return get_node_params("prompt_routing")
    except Exception:
        return {}


class PromptRoutingNode(BaseNode):
    """
    Prompt Routing Node.
    
    Selects and builds the system prompt based on dialog state and state behavior
    from the State Machine Rules Engine.
    """
    
    # Default tone modifiers (fallback if config is missing)
    DEFAULT_TONE_MODIFIERS = {
        "professional": "",
        "helpful": "Будь дружелюбным и готовым помочь.",
        "warm": "Отвечай тепло и с благодарностью.",
        "empathetic": "Прояви эмпатию и понимание. Пользователь может быть расстроен.",
        "curious": "Задавай уточняющие вопросы вежливо и конструктивно.",
        "supportive": "Окажи поддержку и упомяни возможность связаться с оператором.",
        "understanding": "Подтверди, что переключишь пользователя на живого оператора.",
        "patient": "Терпеливо жди и предлагай дополнительную помощь."
    }
    
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        self._instructions = None
        self._tone_modifiers = None

    def _get_instruction(self, state_name: str) -> str:
        """Lazy load instructions using BaseNode utility."""
        if self._instructions is None:
            self._instructions = {
                "INITIAL": self._load_prompt("prompt_instruction_initial.txt"),
                "ANSWER_PROVIDED": self._load_prompt("prompt_instruction_answer_provided.txt"),
                "AWAITING_CLARIFICATION": self._load_prompt("prompt_instruction_awaiting_clarification.txt"),
                "RESOLVED": self._load_prompt("prompt_instruction_resolved.txt"),
                "ESCALATION_NEEDED": self._load_prompt("prompt_instruction_escalation_needed.txt"),
                "ESCALATION_REQUESTED": self._load_prompt("prompt_instruction_escalation_requested.txt"),
                "EMPATHY_MODE": self._load_prompt("prompt_instruction_empathy.txt"),
                "CLARIFY": self._load_prompt("prompt_instruction_clarify.txt"),
                "DEFAULT": self._load_prompt("prompt_instruction_default.txt")
            }
        return self._instructions.get(state_name, self._instructions["DEFAULT"])

    def _get_tone_modifiers(self) -> Dict[str, str]:
        """Lazy load tone modifiers from config."""
        if self._tone_modifiers is None:
            params = _get_params()
            # Try to load from config, fallback to defaults
            config_modifiers = params.get("tone_modifiers", {})
            if config_modifiers:
                self._tone_modifiers = config_modifiers
            else:
                self._tone_modifiers = self.DEFAULT_TONE_MODIFIERS
        return self._tone_modifiers

    def _get_tone_modifier(self, state_behavior: Dict[str, Any]) -> str:
        """Get tone modifier based on state behavior."""
        tone = state_behavior.get("tone", "professional")
        modifiers = self._get_tone_modifiers()
        return modifiers.get(tone, "")

    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Selects and builds the system prompt based on dialog state.
        Uses state_behavior from State Machine for tone selection.
        Uses conversation_history (correct format) instead of session_history.
        """
        params = _get_params()
        max_history = params.get("max_history_messages", DEFAULT_MAX_HISTORY_MESSAGES)
        include_profile = params.get("include_user_profile", True)
        include_entities = params.get("include_entities", True)
        filter_system = params.get("filter_system_messages", True)
        use_tone_modifiers = params.get("use_tone_modifiers", True)
        
        dialog_state = state.get("dialog_state", "INITIAL")
        state_behavior = state.get("state_behavior", {})
        
        # Load instruction using base class utility via helper
        instruction = self._get_instruction(dialog_state)
        
        # Add tone modifier if enabled
        tone_modifier = ""
        if use_tone_modifiers and state_behavior:
            tone_modifier = self._get_tone_modifier(state_behavior)
        
        # Get clean history using proper source
        history_str = _get_formatted_history(state, max_history, filter_system)
        
        # Format additional context
        entities_str = _format_entities(state.get("extracted_entities", {})) if include_entities else ""
        profile_str = _format_profile(state.get("user_profile", {})) if include_profile else ""
        
        # Build final system block
        system_prompt = ""
        
        # Add tone modifier at the beginning
        if tone_modifier:
            system_prompt += f"{tone_modifier}\n\n"
        
        system_prompt += f"{instruction}\n\n"
        
        if profile_str:
            system_prompt += f"--- Информация о пользователе ---\n{profile_str}\n\n"
            
        if entities_str:
            system_prompt += f"--- Извлеченные данные ---\n{entities_str}\n\n"
        
        if history_str:
            system_prompt += f"--- История диалога ---\n{history_str}\n\n"

        return {
            "system_prompt": system_prompt,
            "prompt_hint": state_behavior.get("prompt_hint", "standard")
        }


def _get_formatted_history(state: Dict[str, Any], max_messages: int, filter_system: bool) -> str:
    """
    Get formatted conversation history from the correct source.
    
    Priority:
    1. conversation_history (proper {role, content} format)
    2. session_history (fallback with summaries)
    """
    # Try to use history filter utility
    if get_clean_history_for_prompt:
        clean_history = get_clean_history_for_prompt(state, max_messages)
        if clean_history:
            return _format_message_list(clean_history)
    
    # Fallback: Direct parsing
    # 1. Try conversation_history first (correct format)
    conv_history = state.get("conversation_history", [])
    if conv_history:
        return _format_conversation_history(conv_history, max_messages, filter_system)
    
    # 2. Fallback to session_history summaries
    session_history = state.get("session_history", [])
    if session_history:
        return _format_session_summaries(session_history, max_messages)
    
    return ""


def _format_conversation_history(
    history: List[Dict[str, Any]], 
    max_messages: int,
    filter_system: bool
) -> str:
    """Format conversation_history which has {role, content} structure."""
    if not history:
        return ""
    
    # Filter system messages if requested
    if filter_system and is_system_message:
        filtered = [
            msg for msg in history 
            if not (msg.get("role") == "assistant" and is_system_message(msg.get("content", "")))
        ]
    else:
        filtered = history
    
    # Take last N messages
    recent = filtered[-max_messages:] if len(filtered) > max_messages else filtered
    
    return _format_message_list(recent)


def _format_message_list(messages: List[Dict[str, Any]]) -> str:
    """Format a list of messages to string."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Truncate long messages
        if len(content) > DEFAULT_MAX_MESSAGE_LENGTH:
            content = content[:DEFAULT_MAX_MESSAGE_LENGTH] + "..."
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def _format_session_summaries(sessions: List[Dict[str, Any]], max_sessions: int) -> str:
    """Format session_history which has {session_id, outcome, summary} structure."""
    if not sessions:
        return ""
    
    # Take last N sessions
    recent = sessions[-max_sessions:] if len(sessions) > max_sessions else sessions
    
    lines = []
    for i, session in enumerate(recent, 1):
        summary = session.get("summary", "")
        if summary:
            lines.append(f"[Сессия {i}] {summary}")
    
    return "\n".join(lines)


def _format_entities(entities: Dict[str, Any]) -> str:
    """Format extracted entities."""
    if not entities:
        return ""
    lines = [f"- {k}: {v}" for k, v in entities.items()]
    return "\n".join(lines)


def _format_profile(profile: Dict[str, Any]) -> str:
    """Format user profile."""
    if not profile:
        return ""
    lines = [f"{k}: {v}" for k, v in profile.items()]
    return "\n".join(lines)


# For backward compatibility
route_prompt_node = PromptRoutingNode()
