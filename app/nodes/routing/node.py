"""
Routing Node.

Final routing decision: auto_reply or handoff.
Considers confidence, escalation requests, and document requirements.
"""
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.settings import settings
from app.nodes.routing.logic import decide_action, get_decision_reason
from app.observability.tracing import observe


def _get_params() -> Dict[str, Any]:
    """Get node parameters from centralized config."""
    try:
        from app.services.config_loader.loader import get_node_params
        return get_node_params("routing")
    except Exception:
        return {}


def _get_config() -> Dict[str, Any]:
    """Get node config (text/dict settings) from centralized config."""
    try:
        from app.services.config_loader.loader import get_node_config
        return get_node_config("routing")
    except Exception:
        return {}


class RoutingNode(BaseNode):
    """
    Routing node - executes State Machine decision.
    
    Contracts:
        Input:
            Required:
                - action_recommendation (str): Decision from state_machine
            Optional:
                - escalation_reason (str): Reason for escalation
                - best_doc_metadata (Dict): Metadata from best document
                - confidence (float): Answer confidence
                - confidence_threshold (float): Threshold for auto-reply
                - detected_language (str): User's language
                - answer (str): Existing answer if blocked
                - escalation_requested (bool): User requested escalation
                - safety_violation (bool): Safety violation flag
                - dialog_state (str): Current dialog state
        
        Output:
            Guaranteed:
                - action (str): Final action (auto_reply, handoff, block)
            Conditional:
                - matched_intent (str): Detected intent
                - matched_category (str): Detected category
                - routing_reason (str): Reason for routing decision
                - routing_confidence (float): Confidence used
                - routing_threshold (float): Threshold used
                - escalation_triggered (bool): Was escalation triggered
                - escalation_message (str): Message for user on escalation
                - answer (str): Escalation message as answer
    """
    
    INPUT_CONTRACT = {
        "required": ["action_recommendation"],
        "optional": [
            "escalation_reason",
            "best_doc_metadata",
            "confidence",
            "confidence_threshold",
            "detected_language",
            "answer",
            "escalation_requested",
            "safety_violation",
            "dialog_state"
        ]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["action"],
        "conditional": [
            "matched_intent",
            "matched_category",
            "routing_reason",
            "routing_confidence",
            "routing_threshold",
            "escalation_triggered",
            "escalation_message",
            "answer"
        ]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routing executor - выполняет решение State Machine.
        
        Contracts:
            - Required Inputs: `action_recommendation` (str), `escalation_reason` (str/None)
            - Optional Inputs: `best_doc_metadata` (Dict), `confidence` (float), `confidence_threshold` (float), `detected_language` (str), `answer` (str, if blocked)
            - Guaranteed Outputs: `action` (str), `routing_reason` (str/None), `answer` (str, if escalation/block)
            - Conditional Outputs: `matched_intent`, `matched_category`, `routing_confidence`, `routing_threshold`, `escalation_triggered` (bool), `escalation_message` (str)

        State Machine принимает решение об эскалации и устанавливает action_recommendation.
        Routing только формирует escalation_message и логирует.
        """
        params = _get_params()
        config = _get_config()
        
        # ГЛАВНОЕ: Получаем решение от State Machine
        action_recommendation = state.get("action_recommendation")
        escalation_reason = state.get("escalation_reason")
        
        # Если нет рекомендации (старый flow), используем fallback логику
        if not action_recommendation:
            print("⚠️ No action_recommendation from state_machine, using fallback logic")
            action_recommendation = self._fallback_decision(state, params)
            escalation_reason = escalation_reason or "fallback_decision"
        
        # Метаданные для логирования
        metadata = state.get("best_doc_metadata", {})
        confidence = state.get("confidence", 0.0)
        min_confidence = params.get("min_confidence_auto_reply", 0.3)
        threshold = state.get("confidence_threshold", min_confidence)
        
        # Формируем ответ
        escalation_triggered = False
        escalation_message = None
        
        if action_recommendation == "block":
            print(f"🚫 Request blocked by guardrails/state machine")
            return {
                "action": "block",
                "routing_reason": escalation_reason,
                "answer": state.get("answer") # Pass through existing answer (rejection message)
            }

        if action_recommendation == "handoff":
            escalation_triggered = True
            
            # Получаем сообщение на языке пользователя
            detected_language = state.get("detected_language", "en")
            
            # Если есть активный контекст уточнения, используем язык из него
            clarification_context = state.get("clarification_context", {})
            if clarification_context.get("active") and clarification_context.get("target_language"):
                detected_language = clarification_context["target_language"]
            
            escalation_messages = config.get("escalation_messages", {})
            escalation_message = escalation_messages.get(
                detected_language,
                escalation_messages.get("default", "Transferring to support specialist.")
            )
            
            # Логирование эскалации
            escalation_details = {
                "reason": escalation_reason,
                "confidence": confidence,
                "threshold": threshold,
                "escalation_requested": state.get("escalation_requested", False),
                "safety_violation": state.get("safety_violation", False),
                "language": detected_language,
                "message": escalation_message,
                "dialog_state": state.get("dialog_state")
            }
            
            print(f"🚨 ESCALATION TRIGGERED")
            print(f"   Reason: {escalation_reason}")
            print(f"   Confidence: {confidence:.3f} (Threshold: {threshold:.3f})")
            print(f"   Dialog State: {state.get('dialog_state')}")
            print(f"   Message: {escalation_message}")
            
            # Логируем событие в Langfuse
            try:
                from langfuse import Langfuse
                langfuse = Langfuse()
                langfuse.event(
                    name="escalation_triggered",
                    input=escalation_details,
                    metadata={
                        "node": "routing",
                        "action": "handoff",
                        "source": "state_machine"
                    }
                )
            except Exception as e:
                # Fallback - @observe decorator будет логировать
                print(f"   (Langfuse event logging failed: {e})")
        
        result = {
            "action": action_recommendation,
            "matched_intent": metadata.get("intent"),
            "matched_category": metadata.get("category"),
            "routing_reason": escalation_reason,
            "routing_confidence": confidence,
            "routing_threshold": threshold,
            "escalation_triggered": escalation_triggered,
            "escalation_message": escalation_message
        }
        
        # Explicitly update answer ONLY if we are escalating (replacing generation)
        if escalation_triggered:
             result["answer"] = escalation_message
             
        return result
    
    def _fallback_decision(self, state: Dict[str, Any], params: Dict[str, Any]) -> str:
        """
        Fallback логика принятия решения если state_machine не предоставил рекомендацию.
        Используется для обратной совместимости.
        """
        min_confidence = params.get("min_confidence_auto_reply", 0.3)
        confidence = state.get("confidence", 0.0)
        threshold = state.get("confidence_threshold", min_confidence)
        
        # Проверяем критические сигналы
        if state.get("safety_violation", False):
            return "handoff"
        
        if state.get("escalation_requested", False):
            return "handoff"
        
        metadata = state.get("best_doc_metadata", {})
        if metadata.get("requires_handoff", False):
            return "handoff"
        
        if threshold > 0 and confidence < threshold:
            return "handoff"
        
        return "auto_reply"


# For backward compatibility
route_node = RoutingNode()



