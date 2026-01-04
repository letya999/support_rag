from typing import Dict, Any, List
import json
from app.pipeline.state import State
from app.observability.tracing import observe
from app.integrations.llm import get_llm
from app.nodes.state_machine.states_config import (
    SIGNAL_GRATITUDE, SIGNAL_ESCALATION_REQ, SIGNAL_QUESTION, 
    SIGNAL_REPEATED, SIGNAL_FRUSTRATION
)

@observe(as_type="span")
async def llm_dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Analyzes the dialog history using LLM with Chain of Thought for:
    - User intent and signals (gratitude, repeated questions).
    - Emotion and Sentiment (Phase 5).
    - Safety and Jailbreak (Phase 5).
    - Escalation Decision (Phase 6).
    """
    history = state.get("session_history", []) or []
    current_question = state.get("question", "")
    
    # Prepare messages for context (last 5 messages)
    recent_history = history[-5:] if history else []
    
    history_text = ""
    for msg in recent_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        history_text += f"{role.upper()}: {content}\n"
    
    prompt = f"""You are an advanced Dialogue Analyzer for an AI Customer Support Agent.
Your task is to analyze the user's LATEST message in the context of the conversation history.

You must determine:
1. **User Signals**: gratitude, questions, repetition.
2. **Emotion & Sentiment**: Is the user angry, frustrated, or happy?
3. **Safety**: Is the user trying to abuse, jailbreak, or ask harmful things?
4. **Escalation**: Should this conversation be handed over to a human specialist IMMEDIATELY?

Conversation History:
{history_text}
USER (Latest): {current_question}

Perform a **Chain of Thought** reasoning step before giving the final JSON.
Reason about:
- The user's emotional state (look for capitalization, punctuation, specific words).
- Whether the query is safe.
- Whether the user explicitly wants a human OR if the situation implies they need one (high frustration).
- Decide on the final action.

Output a valid JSON object with this schema:
{{
  "chain_of_thought": "Your step-by-step reasoning process...",
  "signals": {{
      "{SIGNAL_GRATITUDE}": boolean,
      "{SIGNAL_ESCALATION_REQ}": boolean,   // Explicit request only
      "{SIGNAL_QUESTION}": boolean,
      "{SIGNAL_REPEATED}": boolean
  }},
  "sentiment": {{
      "label": "positive" | "neutral" | "negative" | "frustrated" | "angry",
      "score": float (0.0 to 1.0, where 1.0 is max intensity of the label)
  }},
  "safety": {{
      "violation": boolean,
      "reason": string | null
  }},
  "escalation": {{
      "decision": "escalate" | "auto_reply",
      "reason": string | null
  }}
}}

Constraints:
- "{SIGNAL_ESCALATION_REQ}" is TRUE only if user EXPLICITLY asks for human/agent/operator.
- "escalation.decision" should be "escalate" if:
    a) "{SIGNAL_ESCALATION_REQ}" is true
    b) "sentiment.label" is "angry" with high score (>0.7)
    c) "safety.violation" is true
    d) The user seems stuck in a loop ({SIGNAL_REPEATED} is true AND attempts > 2)
- Otherwise "escalation.decision" is "auto_reply".
"""

    try:
        # Using standard LLM integration
        llm = get_llm(temperature=0.0, json_mode=True)
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
        result = {
            "dialog_analysis": {
                SIGNAL_GRATITUDE: signals.get(SIGNAL_GRATITUDE, False),
                SIGNAL_ESCALATION_REQ: signals.get(SIGNAL_ESCALATION_REQ, False),
                SIGNAL_QUESTION: signals.get(SIGNAL_QUESTION, True),
                SIGNAL_REPEATED: signals.get(SIGNAL_REPEATED, False),
                SIGNAL_FRUSTRATION: sentiment.get("label") in ["frustrated", "angry"],
                "chain_of_thought": analysis_data.get("chain_of_thought", "")
            },
            # Phase 5 & 6 State Extensions
            "sentiment": sentiment,
            "safety_violation": safety.get("violation", False),
            "safety_reason": safety.get("reason"),
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
                SIGNAL_REPEATED: False
            },
            "sentiment": {"label": "neutral", "score": 0.0},
            "safety_violation": False,
            "safety_reason": None,
            "escalation_decision": "auto_reply",
            "escalation_reason": "fallback"
        }
