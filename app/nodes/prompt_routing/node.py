from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.nodes.prompt_routing.prompts import SYSTEM_INSTRUCTIONS

class PromptRoutingNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Selects and builds the system prompt based on dialog state.
        """
        dialog_state = state.get("dialog_state", "INITIAL")
        # Fallback to DEFAULT if state not found
        instruction = SYSTEM_INSTRUCTIONS.get(dialog_state, SYSTEM_INSTRUCTIONS["DEFAULT"])
        
        # Enrich with context
        history_str = _format_history(state.get("session_history", []))
        entities_str = _format_entities(state.get("extracted_entities", {}))
        profile_str = _format_profile(state.get("user_profile", {}))
        
        # Build final system block
        system_prompt = f"{instruction}\n\n"
        
        if profile_str:
            system_prompt += f"--- Информация о пользователе ---\n{profile_str}\n\n"
            
        if entities_str:
            system_prompt += f"--- Извлеченные данные ---\n{entities_str}\n\n"
        
        if history_str:
            system_prompt += f"--- История диалога ---\n{history_str}\n\n"

        return {"system_prompt": system_prompt}

def _format_history(history: List[Dict[str, Any]]) -> str:
    if not history:
        return ""
    # Take last 3 messages
    recent = history[-3:]
    lines = []
    for msg in recent:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)

def _format_entities(entities: Dict[str, Any]) -> str:
    if not entities:
        return ""
    lines = [f"- {k}: {v}" for k, v in entities.items()]
    return "\n".join(lines)

def _format_profile(profile: Dict[str, Any]) -> str:
    if not profile:
        return ""
    lines = [f"{k}: {v}" for k, v in profile.items()]
    return "\n".join(lines)

# For backward compatibility
route_prompt_node = PromptRoutingNode()
