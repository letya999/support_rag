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
from langchain_core.messages import HumanMessage, AIMessage, trim_messages, BaseMessage
import inspect

# Default config values
DEFAULT_MAX_HISTORY_MESSAGES = 5
DEFAULT_MAX_MESSAGE_LENGTH = 300
MAX_HISTORY_TOKENS = 500

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
    
    Contracts:
        Input:
            Required:
                - question (str): User question
            Optional:
                - dialog_state (str): Current dialog state
                - state_behavior (Dict): Behavior hints from state machine
                - conversation_history (List[Dict]): Message history
                - session_history (List[Dict]): Alias for history
                - _session_history_loader (Callable): Lazy history loader
                - detected_language (str): User's language
                - docs (List[str]): Retrieved documents
                - aggregated_query (str): Enhanced query
                - user_profile (Dict): User profile data
                - extracted_entities (Dict): Extracted entities
        
        Output:
            Guaranteed:
                - system_prompt (str): Built system prompt
                - human_prompt (str): Built human prompt with context
            Conditional:
                - prompt_hint (str): State-specific hints
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": [
            "dialog_state",
            "state_behavior",
            "conversation_history",
            "session_history",
            "_session_history_loader",
            "detected_language",
            "docs",
            "aggregated_query",
            "user_profile",
            "extracted_entities"
        ]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["system_prompt", "human_prompt"],
        "conditional": ["prompt_hint"]
    }
    
    # Default tone modifiers (fallback if config is missing)
    DEFAULT_TONE_MODIFIERS = {
        "professional": "",
        "helpful": "Be direct and helpful.",
        "warm": "Be polite.",
        "empathetic": "Be supportive but concise.",
        "curious": "Ask clarifying questions if needed.",
        "supportive": "Offer support.",
        "understanding": "Acknowledge the request.",
        "patient": "Be patient."
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
                "SAFETY_VIOLATION": self._load_prompt("prompt_instruction_safety_violation.txt"),
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

    def _count_tokens(self, messages: List[BaseMessage]) -> int:
        """Simple token counter based on characters."""
        total = 0
        for m in messages:
            if isinstance(m.content, str):
                total += len(m.content) // 4
        return total

    def _prepare_history(self, history: List[Any], max_tokens: int = MAX_HISTORY_TOKENS) -> str:
        """Prepare history with trimming using langchain_core."""
        if not history:
            return ""

        # Convert to LangChain messages
        messages = []
        for m in history:
            if isinstance(m, BaseMessage):
                messages.append(m)
                continue

            if isinstance(m, dict):
                role = m.get("role")
                content = m.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant" or role == "system":
                    # Treat system messages as AI messages for history context or skip
                    # Assuming assistant for context
                    messages.append(AIMessage(content=content))
        
        # Trim messages
        try:
            trimmed = trim_messages(
                messages,
                max_tokens=max_tokens,
                strategy="last",
                token_counter=self._count_tokens,
                include_system=False,
                start_on="human"
            )
        except Exception:
             # Fallback if trim fails or not configured
             trimmed = messages[-5:]

        return self._format_messages(trimmed)

    def _format_messages(self, messages: List[BaseMessage]) -> str:
        """Format LangChain messages to string."""
        lines = []
        for msg in messages:
            role = "USER" if isinstance(msg, HumanMessage) else "ASSISTANT"
            content = msg.content
            if len(content) > DEFAULT_MAX_MESSAGE_LENGTH:
                 content = content[:DEFAULT_MAX_MESSAGE_LENGTH] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Selects and builds the system prompt based on dialog state.
        Uses state_behavior from State Machine for tone selection.
        Uses conversation_history (correct format) instead of session_history.
        """
        params = _get_params()
        
        # Resolve lazy session history if needed (though we prefer conversation_history)
        # Note: Priority is conversation_history (current flow), then session_history (archived)
        # Check if we need to load session_history fallback
        session_history = state.get("session_history")
        if not session_history and "_session_history_loader" in state:
            loader = state["_session_history_loader"]
            if callable(loader):
                try:
                    coro_or_val = loader()
                    if inspect.isawaitable(coro_or_val):
                        session_history = await coro_or_val
                    else:
                        session_history = coro_or_val
                except Exception as e:
                    print(f"Failed to lazy load session history: {e}")
        
        include_profile = params.get("include_user_profile", True)
        include_entities = params.get("include_entities", True)
        use_tone_modifiers = params.get("use_tone_modifiers", True)
        max_history_tokens = params.get("max_history_tokens", MAX_HISTORY_TOKENS)
        
        dialog_state = state.get("dialog_state", "INITIAL")
        state_behavior = state.get("state_behavior", {})
        
        # Load instruction using base class utility via helper
        instruction = self._get_instruction(dialog_state)
        
        # Add tone modifier if enabled
        tone_modifier = ""
        if use_tone_modifiers and state_behavior:
            tone_modifier = self._get_tone_modifier(state_behavior)
        
        # Get clean history
        # Priority: conversation_history > session_history
        conv_history = state.get("conversation_history", [])
        if not conv_history and session_history:
            # Adapt session_history to dict format if needed
             # Assuming session_history is strictly List[Dict]
             conv_history = session_history
        
        history_str = self._prepare_history(conv_history, max_tokens=max_history_tokens)
        
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
            system_prompt += f"--- User Profile ---\n{profile_str}\n\n"
            
        if entities_str:
            system_prompt += f"--- Extracted Data ---\n{entities_str}\n\n"
        
        if history_str:
            system_prompt += f"--- Conversation History ---\n{history_str}\n\n"

        # Localization Directive - always enforce detected language
        lang = state.get("detected_language", "ru")
        lang_map = {
            "en": "English",
            "ru": "Russian (русский)",
            "es": "Spanish (español)",
            "de": "German (Deutsch)",
            "fr": "French (français)",
            "it": "Italian (italiano)",
            "pt": "Portuguese (português)",
            "uk": "Ukrainian (українська)"
        }
        lang_name = lang_map.get(lang, f"the user's language ({lang})")
        system_prompt += f"\n\nIMPORTANT: You MUST respond in {lang_name} language."

        # Build human prompt with docs
        question = state.get("aggregated_query") or state.get("question")
        docs = state.get("docs", [])
        docs_str = "\n\n".join(docs)
        human_prompt = f"Context:\n{docs_str}\n\nQuestion: {question}"

        return {
            "system_prompt": system_prompt,
            "human_prompt": human_prompt,  # NEW
            "prompt_hint": state_behavior.get("prompt_hint", "standard")
        }


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
