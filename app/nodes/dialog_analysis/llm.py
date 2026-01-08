from typing import Dict, Any, List
import json
from app.pipeline.state import State
from app.observability.tracing import observe
from app.integrations.llm import get_llm
from app.services.config_loader.loader import get_node_params
from app.nodes.state_machine.states_config import (
    SIGNAL_GRATITUDE, SIGNAL_ESCALATION_REQ, SIGNAL_QUESTION, 
    SIGNAL_REPEATED, SIGNAL_FRUSTRATION
)
from app.nodes.dialog_analysis.loop_detector import detect_topic_loop

@observe(as_type="span")
async def llm_dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Analyzes the dialog history using LLM with optimized prompt for:
    - User intent and signals (gratitude, repeated questions).
    - Emotion and Sentiment.
    - Safety and Policy Violations.
    - Escalation Decision.
    
    Uses configurable model and temperature from config.yaml.
    """
    # Priority: conversation_history (active) > session_history (archived)
    history = state.get("conversation_history") or state.get("session_history", []) or []
    print(f"🔍 dialog_analysis (LLM): Got {len(history)} history messages")
    current_question = state.get("question", "")
    
    # Load config
    params = get_node_params("dialog_analysis")
    llm_config = params.get("llm", {})
    model = llm_config.get("model", "gpt-4o-mini")
    temperature = llm_config.get("temperature", 0.0)
    
    # Prepare messages for context (last 5 messages)
    recent_history = history[-5:] if history else []
    
    history_text = ""
    for msg in recent_history:
        if isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
        else:
            # Handle object-based messages (e.g. LangChain HumanMessage/AIMessage)
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            
        history_text += f"{role.upper()}: {content}\n"

    import os

    def _load_prompt(filename: str) -> str:
        path = os.path.join(os.path.dirname(__file__), filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    prompt_template = _load_prompt("prompt_analysis.txt")
    prompt = prompt_template.format(
        history_text=history_text,
        current_question=current_question,
        SIGNAL_GRATITUDE=SIGNAL_GRATITUDE,
        SIGNAL_ESCALATION_REQ=SIGNAL_ESCALATION_REQ,
        SIGNAL_QUESTION=SIGNAL_QUESTION,
        SIGNAL_REPEATED=SIGNAL_REPEATED
    )


    try:
        # Using configured model and temperature
        llm = get_llm(model=model, temperature=temperature, json_mode=True)
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        
        # Parse JSON
        analysis_content = response.content
        if "```json" in analysis_content:
            analysis_content = analysis_content.split("```json")[1].split("```")[0].strip()
        elif "```" in analysis_content:
            analysis_content = analysis_content.split("```")[1].split("```")[0].strip()
            
        analysis_data = json.loads(analysis_content)
        
        # Extract components
        signals = analysis_data.get("signals", {})
        sentiment = analysis_data.get("sentiment", {"label": "neutral", "score": 0.0})
        safety = analysis_data.get("safety", {"violation": False, "reason": None})
        escalation = analysis_data.get("escalation", {"decision": "auto_reply", "reason": None})
        
        # Map back to standard dict
        escalation_req = signals.get(SIGNAL_ESCALATION_REQ, False)
        
        # Topic loop detection (NEW!)
        topic_loop_detected = False
        if params.get("detect_topic_loop", True):
            loop_result = await detect_topic_loop(
                current_question=current_question,
                conversation_history=history,
                similarity_threshold=params.get("topic_loop_similarity_threshold", 0.85),  # Higher for English
                window_size=params.get("topic_loop_window_size", 4),
                min_messages_for_loop=params.get("topic_loop_min_messages", 3),
                translated_query=state.get("translated_query"),  # From query_translation node
                detected_language=state.get("detected_language")  # From language_detection node
            )
            topic_loop_detected = loop_result["topic_loop_detected"]
            # Store additional metadata for debugging
            state["loop_detection_metadata"] = loop_result
        
        result = {
            "dialog_analysis": {
                SIGNAL_GRATITUDE: signals.get(SIGNAL_GRATITUDE, False),
                SIGNAL_ESCALATION_REQ: escalation_req,
                SIGNAL_QUESTION: signals.get(SIGNAL_QUESTION, True),
                SIGNAL_REPEATED: signals.get(SIGNAL_REPEATED, False),
                SIGNAL_FRUSTRATION: sentiment.get("label") in ["frustrated", "angry"],
                "topic_loop_detected": topic_loop_detected  # NEW!
            },
            # Phase 5 & 6 State Extensions
            "sentiment": sentiment,
            "safety_violation": safety.get("violation", False),
            "safety_reason": safety.get("reason"),
            "escalation_requested": escalation_req,  # For routing node
            "escalation_decision": escalation.get("decision", "auto_reply"),
            "escalation_reason": escalation.get("reason")
        }
                
        return result

    except Exception as e:
        print(f"LLM Dialog Analysis verification failed: {e}. Falling back to default.")
        # Fallback to safe defaults
        return {
            "dialog_analysis": {
                SIGNAL_GRATITUDE: False,
                SIGNAL_ESCALATION_REQ: False,
                SIGNAL_QUESTION: True,
                SIGNAL_FRUSTRATION: False,
                SIGNAL_REPEATED: False,
                "topic_loop_detected": False  # NEW!
            },
            "sentiment": {"label": "neutral", "score": 0.0},
            "safety_violation": False,
            "safety_reason": None,
            "escalation_requested": False,  # For routing node
            "escalation_decision": "auto_reply",
            "escalation_reason": "fallback"
        }
