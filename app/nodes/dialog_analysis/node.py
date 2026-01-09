from typing import Dict, Any, List
import re
from app.nodes.base_node import BaseNode
from app.pipeline.state import State
from app.observability.tracing import observe
from app.services.config_loader.conversation_config import conversation_config
from app.services.config_loader.loader import get_node_params
from app.nodes.dialog_analysis.llm import llm_dialog_analysis_node
from app.nodes.state_machine.states_config import (
    SIGNAL_GRATITUDE, SIGNAL_ESCALATION_REQ, SIGNAL_QUESTION, 
    SIGNAL_REPEATED, SIGNAL_FRUSTRATION
)
from app.nodes.dialog_analysis.rules.question_detector import is_question
from app.nodes.dialog_analysis.loop_detector import detect_topic_loop

class DialogAnalysisNode(BaseNode):
    """
    Analyzes dialog for signals like gratitude, escalation, frustration.
    
    Contracts:
        Input:
            Required:
                - question (str): Current user question
            Optional:
                - conversation_history (List[Dict]): Message history
                - session_history (List[Dict]): Alias for history
                - translated_query (str): For translated loop detection
        
        Output:
            Guaranteed:
                - dialog_analysis (Dict): Analysis results with signal flags
                - sentiment (Dict): Sentiment analysis result
                - safety_violation (bool): Safety check result
                - escalation_requested (bool): Whether escalation was requested
                - escalation_decision (str): Decision for routing
            Conditional:
                - safety_reason (str): Reason if safety violation
                - escalation_reason (str): Reason for escalation
                - loop_detection_metadata (Dict): Loop detection details
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": ["conversation_history", "session_history", "translated_query"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": [
            "dialog_analysis",
            "sentiment", 
            "safety_violation",
            "escalation_requested",
            "escalation_decision"
        ],
        "conditional": [
            "safety_reason",
            "escalation_reason",
            "loop_detection_metadata"
        ]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatcher for dialog analysis.
        """
        if conversation_config.use_llm_analysis:
            return await llm_dialog_analysis_node(state)
        else:
            return await regex_dialog_analysis_node(state)

async def regex_dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Analyzes the dialog history for signals like gratitude, escalation requests, etc.
    Does NOT use LLM, pure Python logic.
    """
    params = get_node_params("dialog_analysis")
    
    # Get keywords from nested structure (new format) or flat structure (fallback)
    keywords = params.get("keywords", {})
    
    history = state.get("conversation_history") or state.get("session_history", []) or []
    print(f"🔍 dialog_analysis (regex): Got {len(history)} history messages")
    current_question = state.get("question", "").lower()
    
    # Defaults
    analysis = {
        SIGNAL_GRATITUDE: False,
        SIGNAL_ESCALATION_REQ: False,
        SIGNAL_QUESTION: False,
        SIGNAL_FRUSTRATION: False, 
        SIGNAL_REPEATED: False,
        "topic_loop_detected": False  # New field
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
    analysis[SIGNAL_QUESTION] = is_question(state.get("question", ""))

    # 4. Frustration detection
    frustration_keywords = keywords.get("frustration", ["тупой", "stupid"])
    if any(k in current_question for k in frustration_keywords):
        analysis[SIGNAL_FRUSTRATION] = True

    # 5. Repeated question check
    if params.get("detect_repeated_questions", True):
        last_user_msg = None
        for msg in reversed(history):
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content", "").lower()
            else:
                role = getattr(msg, "type", "unknown")
                content = getattr(msg, "content", "").lower()

            if role == "user":
                last_user_msg = content
                break
                
        if last_user_msg:
            def clean(s): return re.sub(r'[^\w\s]', '', s).strip()
            if clean(current_question) == clean(last_user_msg):
                analysis[SIGNAL_REPEATED] = True
    
    # 6. Topic loop detection (NEW!)
    if params.get("detect_topic_loop", True):
        loop_result = await detect_topic_loop(
            current_question=state.get("question", ""),
            conversation_history=history,
            similarity_threshold=params.get("topic_loop_similarity_threshold", 0.8),
            window_size=params.get("topic_loop_window_size", 4),
            min_messages_for_loop=params.get("topic_loop_min_messages", 3)
        )
        analysis["topic_loop_detected"] = loop_result["topic_loop_detected"]
        # Store additional metadata for debugging
        state["loop_detection_metadata"] = loop_result
    
    return {
        "dialog_analysis": analysis,
        "sentiment": {"label": "frustrated" if analysis[SIGNAL_FRUSTRATION] else "neutral", "score": 0.5},
        "safety_violation": False,
        "safety_reason": None,
        "escalation_requested": analysis[SIGNAL_ESCALATION_REQ],  # For routing node
        "escalation_decision": "escalate" if analysis[SIGNAL_ESCALATION_REQ] else "auto_reply",
        "escalation_reason": "regex_keyword_match" if analysis[SIGNAL_ESCALATION_REQ] else None
    }

# For backward compatibility
dialog_analysis_node = DialogAnalysisNode()
