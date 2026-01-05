from typing import Dict, Any, List
import re
from app.nodes.base_node import BaseNode
from app.pipeline.state import State
from app.observability.tracing import observe
from app.pipeline.config_proxy import conversation_config
from app.services.config_loader.loader import get_node_params
from app.nodes.dialog_analysis.llm import llm_dialog_analysis_node
from app.nodes.state_machine.states_config import (
    SIGNAL_GRATITUDE, SIGNAL_ESCALATION_REQ, SIGNAL_QUESTION, 
    SIGNAL_REPEATED, SIGNAL_FRUSTRATION
)

class DialogAnalysisNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatcher for dialog analysis.
        """
        if conversation_config.use_llm_analysis:
            return await llm_dialog_analysis_node(state)
        else:
            return regex_dialog_analysis_node(state)

def regex_dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Analyzes the dialog history for signals like gratitude, escalation requests, etc.
    Does NOT use LLM, pure Python logic.
    """
    params = get_node_params("dialog_analysis")
    
    # Get keywords from nested structure (new format) or flat structure (fallback)
    keywords = params.get("keywords", {})
    
    history = state.get("session_history", []) or []
    current_question = state.get("question", "").lower()
    
    # Defaults
    analysis = {
        SIGNAL_GRATITUDE: False,
        SIGNAL_ESCALATION_REQ: False,
        SIGNAL_QUESTION: False,
        SIGNAL_FRUSTRATION: False, 
        SIGNAL_REPEATED: False
    }

    # 1. Gratitude check
    gratitude_keywords = keywords.get("gratitude", ["спасибо", "thank"])
    if any(k in current_question for k in gratitude_keywords):
        analysis[SIGNAL_GRATITUDE] = True

    # 2. Escalation check
    escalation_keywords = keywords.get("escalation", ["оператор", "human"])
    if any(k in current_question for k in escalation_keywords):
        analysis[SIGNAL_ESCALATION_REQ] = True

    # 3. Question check
    question_starters = ["что", "как", "почему", "когда", "можно", "можешь", "what", "how", "why", "when", "can"]
    if "?" in current_question or any(current_question.strip().startswith(w) for w in question_starters):
        analysis[SIGNAL_QUESTION] = True

    # 4. Frustration detection
    frustration_keywords = keywords.get("frustration", ["тупой", "stupid"])
    if any(k in current_question for k in frustration_keywords):
        analysis[SIGNAL_FRUSTRATION] = True

    # 5. Repeated question check
    if params.get("detect_repeated_questions", True):
        last_user_msg = None
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "").lower()
                break
                
        if last_user_msg:
            def clean(s): return re.sub(r'[^\w\s]', '', s).strip()
            if clean(current_question) == clean(last_user_msg):
                analysis[SIGNAL_REPEATED] = True
    
    return {
        "dialog_analysis": analysis,
        "sentiment": {"label": "frustrated" if analysis[SIGNAL_FRUSTRATION] else "neutral", "score": 0.5},
        "safety_violation": False,
        "safety_reason": None,
        "escalation_decision": "escalate" if analysis[SIGNAL_ESCALATION_REQ] else "auto_reply",
        "escalation_reason": "regex_keyword_match" if analysis[SIGNAL_ESCALATION_REQ] else None
    }

# For backward compatibility
dialog_analysis_node = DialogAnalysisNode()
