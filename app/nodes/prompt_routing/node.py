"""
Prompt Routing Node.

Selects and builds the system prompt based on dialog state.
Uses correct conversation_history format instead of session_history.
"""
from typing import Dict, Any, Literal, Optional
from app.nodes.base_node import BaseNode
from app.integrations.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from app.services.config_loader.loader import load_shared_config
from app.utils.prompt_sanitization import sanitize_for_prompt, sanitize_list, sanitize_dict_values
import logging
import json
try:
    from app._shared_config.history_filter import get_clean_history_for_prompt, is_system_message
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
            "extracted_entities",
            "collected_slots",
            "clarification_context"
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
                "NEEDS_CLARIFICATION": self._load_prompt("prompt_instruction_clarify.txt"),  # Add exact match
                "CLARIFY": self._load_prompt("prompt_instruction_clarify.txt"),
                "answer_and_handoff": self._load_prompt("prompt_instruction_answer_and_handoff.txt"),
                "DEFAULT": self._load_prompt("prompt_instruction_default.txt")
            }
        return self._instructions.get(state_name, self._instructions["DEFAULT"])

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the prompt routing logic.
        
        Args:
            state: The current conversation state.
            
        Returns:
            Dict containing system_prompt, human_prompt, and prompt_hint.
        """
        question = state.get("question")
        dialog_state = state.get("dialog_state", "INITIAL")
        state_behavior = state.get("state_behavior", {})

        # Sanitize all user-controlled inputs to prevent prompt injection
        user_profile = sanitize_dict_values(state.get("user_profile", {}))
        extracted_entities = sanitize_dict_values(state.get("extracted_entities", {}))
        collected_slots = sanitize_dict_values(state.get("collected_slots", {}))

        # Use aggregated query if available, else original question
        raw_query = state.get("aggregated_query") or question
        current_query = sanitize_for_prompt(raw_query) if raw_query else ""
        
        # 1. Get base instruction based on state
        system_prompt = self._get_instruction(dialog_state)
        
        # 2. Append User Profile if present
        if user_profile:
            profile_str = _format_profile(user_profile)
            if profile_str:
                system_prompt += f"\n\nUser Profile:\n{profile_str}"
                
        # 3. Append Entities
        if extracted_entities:
            entities_str = _format_entities(extracted_entities)
            if entities_str:
                system_prompt += f"\n\nContext Entities:\n{entities_str}"
                
        # 4. Append Collected Slots & Clarification Answers
        clarification_context = state.get("clarification_context", {})
        all_details = collected_slots.copy()

        if clarification_context and clarification_context.get("answers"):
            # Sanitize clarification answers as they contain user input
            sanitized_answers = sanitize_dict_values(clarification_context["answers"])
            all_details.update(sanitized_answers)

        if all_details:
             slots_str = "\n".join([f"- {k}: {v}" for k, v in all_details.items()])
             system_prompt += f"\n\nKnown Details:\n{slots_str}"

        # 5. Append Conversation History
        if get_clean_history_for_prompt:
            history_msgs = get_clean_history_for_prompt(state, max_messages=DEFAULT_MAX_HISTORY_MESSAGES)
            if history_msgs:
                history_str = ""
                for msg in history_msgs:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    history_str += f"{role.capitalize()}: {content}\n"
                
                if history_str:
                    system_prompt += f"\n\nConversation History:\n{history_str}"

        # 6. Build human prompt with docs
        docs = state.get("docs", [])

        if dialog_state in ["NEEDS_CLARIFICATION", "CLARIFY"]:
             # If we are clarifying, DO NOT include docs.
             docs_str = ""

             # Check for pending questions (Strict Mode)
             # Try legacy pending_questions OR new clarification_context
             active_questions = state.get("pending_questions")
             if not active_questions:
                 ctx = state.get("clarification_context", {})
                 if ctx.get("active"):
                     idx = ctx.get("current_index", 0)
                     qs = ctx.get("questions", [])
                     if idx < len(qs):
                         active_questions = [qs[idx]]

             if active_questions:
                 # STRICT MODE: Force LLM to just ask the specific question
                 # Sanitize the target question as it may have come from user-provided metadata
                 target_question = sanitize_for_prompt(active_questions[0])
                 detected_lang = state.get("detected_language", "en")

                 system_prompt = (
                     "You are a precise technical assistant. "
                     "Your ONLY task is to ask the specific question provided below. "
                     f"Translate the question to '{detected_lang}' (Russian/Spanish/etc) to match the user. "
                     "Do NOT answer the question. Do NOT add pleasantries. Do NOT hallucinate new questions."
                 )

                 # We include the user's last input purely for context, but explicitly tell LLM to ignore it for generation
                 human_prompt = (
                     f"User's previous input: {current_query}\n"
                     "--------------------------------------------------\n"
                     f"TASK: Ask this EXACT question: \"{target_question}\"\n"
                     "Output:"
                 )
             else:
                 # Fallback to standard clarification flow (if node didn't run or list empty)
                 human_prompt = f"User's previous input: {current_query}"

                 clarification_task = state.get("clarification_task", {})
                 questions = clarification_task.get("clarifying_questions", [])
                 if not questions:
                     best_doc = state.get("best_doc_metadata", {})
                     questions = best_doc.get("clarifying_questions", [])

                 system_prompt = self._get_instruction("NEEDS_CLARIFICATION")
                 if questions:
                     # Sanitize questions as they may come from user-provided metadata
                     sanitized_questions = sanitize_list(questions)
                     questions_str = "\n".join([f"- {q}" for q in sanitized_questions])
                     system_prompt += f"\n\nRequired Clarifying Questions:\n{questions_str}"
        else:
             # Sanitize docs to prevent injection through retrieved content
             sanitized_docs = sanitize_list(docs)
             docs_str = "\n\n".join(sanitized_docs) if sanitized_docs else ""
             if docs_str:
                 human_prompt = f"Context:\n{docs_str}\n\nQuestion: {current_query}"
             else:
                 human_prompt = f"Question: {current_query}"

        return {
            "system_prompt": system_prompt,
            "human_prompt": human_prompt,
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
