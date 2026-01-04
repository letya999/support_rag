from typing import Dict, Any, List
import json
from app.pipeline.state import State
from app.observability.tracing import observe
from app.integrations.openai import llm_client

@observe(as_type="span")
async def llm_dialog_analysis_node(state: State) -> Dict[str, Any]:
    """
    Analyzes the dialog history using LLM for deeper understanding of user intent and sentiment.
    """
    history = state.get("session_history", []) or []
    current_question = state.get("question", "")
    
    # Prepare messages for context (last 3 interaction pairs max)
    context_msgs = []
    # reverse history to get latest first, take last few, then reverse back
    # history structure is list of dicts with role/content
    
    # Get last 5 messages to provide context
    recent_history = history[-5:] if history else []
    
    history_text = ""
    for msg in recent_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        history_text += f"{role.upper()}: {content}\n"
    
    prompt = f"""You are a dialog analyzer for a customer support bot.
Analyze the user's LATEST message based on the conversation history.

Conversation History:
{history_text}
USER (Latest): {current_question}

Determine the following signals and return as JSON:
1. "is_gratitude": true if user is thanking or expressing satisfaction.
2. "escalation_requested": true if user explicitly asks for a human/operator/agent.
3. "is_question": true if user is asking a question or requesting info.
4. "frustration_detected": true if user shows anger, frustration, or uses insults.
5. "repeated_question": true if user is essentially repeating a previous unanswered question despite the history.

Return ONLY the JSON object.
Example:
{{
  "is_gratitude": false,
  "escalation_requested": false,
  "is_question": true,
  "frustration_detected": false,
  "repeated_question": false
}}
"""

    try:
        response = await llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            json_mode=True
        )
        
        # Parse JSON
        analysis_content = response.content
        # Remove markdown code blocks if present
        if "```json" in analysis_content:
            analysis_content = analysis_content.split("```json")[1].split("```")[0].strip()
        elif "```" in analysis_content:
            analysis_content = analysis_content.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(analysis_content)
        
        # Fallback fields if missing
        required_keys = ["is_gratitude", "escalation_requested", "is_question", "frustration_detected", "repeated_question"]
        for key in required_keys:
            if key not in analysis:
                analysis[key] = False
                
        return {"dialog_analysis": analysis}

    except Exception as e:
        print(f"LLM Dialog Analysis verification failed: {e}. Falling back to default.")
        # Fallback to safe defaults
        return {
            "dialog_analysis": {
                "is_gratitude": False,
                "escalation_requested": False,
                "is_question": True,
                "frustration_detected": False,
                "repeated_question": False
            }
        }
