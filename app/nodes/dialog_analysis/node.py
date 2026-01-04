from typing import Dict, Any, List
import re
from app.pipeline.state import State
from app.observability.tracing import observe
from app.config.conversation_config import conversation_config
from app.nodes.dialog_analysis.llm import llm_dialog_analysis_node

def regex_dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Analyzes the dialog history for signals like gratitude, escalation requests, etc.
    Does NOT use LLM, pure Python logic.
    """
    history = state.get("session_history", []) or []
    current_question = state.get("question", "").lower()
    
    # Defaults
    analysis = {
        "is_gratitude": False,
        "escalation_requested": False,
        "is_question": False,
        "frustration_detected": False, 
        "repeated_question": False
    }

    # 1. Gratitude check
    # Russian and English keywords
    gratitude_keywords = [
        "thank", "thanks", "thx", "appreciate", "good job",
        "спасибо", "благодарю", "спс", "класс", "молодец"
    ]
    if any(k in current_question for k in gratitude_keywords):
        analysis["is_gratitude"] = True

    # 2. Escalation check
    escalation_keywords = [
        "human", "agent", "person", "operator", "talk to someone", "support team",
        "человек", "оператор", "агент", "сотрудник", "менеджер", "позови", "переключи"
    ]
    if any(k in current_question for k in escalation_keywords):
        analysis["escalation_requested"] = True

    # 3. Question check
    question_starters = [
        "what", "how", "why", "when", "can", "is", "are", "do", "does",
        "что", "как", "почему", "когда", "можно", "можешь", "расскажи", "подскажи"
    ]
    if "?" in current_question or any(current_question.strip().startswith(w) for w in question_starters):
        analysis["is_question"] = True

    # 4. Frustration detection (simple keyword based)
    frustration_keywords = [
        "stupid", "useless", "bad", "wrong", "broke", "hate", "idiot",
        "тупой", "глупый", "бесполезный", "плохой", "ужас", "бред", "идиот"
    ]
    if any(k in current_question for k in frustration_keywords):
        analysis["frustration_detected"] = True

    # 5. Repeated question check
    # Check if the current user message is very similar to the last user message
    last_user_msg = None
    # Iterate backwards through history to find the last user message
    for msg in reversed(history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "").lower()
            break
            
    if last_user_msg:
        # Simple exact match or subset check for MVP
        # Basic normalization (remove punctuation, spaces)
        def clean(s): return re.sub(r'[^\w\s]', '', s).strip()
        if clean(current_question) == clean(last_user_msg):
            analysis["repeated_question"] = True
    
    return {"dialog_analysis": analysis}

@observe(as_type="span")
async def dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Dispatcher for dialog analysis.
    """
    if conversation_config.use_llm_analysis:
        return await llm_dialog_analysis_node(state)
    else:
        return regex_dialog_analysis_node(state)
