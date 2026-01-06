from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.services.config_loader.loader import get_node_params
from app.nodes.state_machine.rules_engine import get_rules_engine, RulesEngine
from app.nodes.state_machine.states_config import (
    TRANSITION_RULES, STATE_CONFIG, 
    INITIAL, ANSWER_PROVIDED, ESCALATION_NEEDED, ESCALATION_REQUESTED,
    SAFETY_VIOLATION, EMPATHY_MODE, BLOCKED
)



class StateMachineNode(BaseNode):
    """
    State Machine Node for managing conversation state transitions.
    
    Uses a declarative Rules Engine (rules.yaml) to evaluate dialog analysis
    signals and determine the next state. Falls back to Python-based rules
    if the YAML configuration is unavailable.
    """
    
    def __init__(self):
        self._rules_engine: RulesEngine = get_rules_engine()
    
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main State Machine logic.
        
        Evaluates dialog analysis signals against rules to determine:
        1. The next conversation state
        2. Updated attempt count
        3. State behavior hints for downstream nodes (prompt_routing)
        """
        # Inputs
        analysis = state.get("dialog_analysis", {})
        current_state = state.get("dialog_state") or INITIAL
        attempt_count = state.get("attempt_count") or 0
        escalation_decision = state.get("escalation_decision", "auto_reply")
        
        # Phase 5 inputs
        safety_violation = state.get("safety_violation", False)
        sentiment = state.get("sentiment", {})
        guardrails_blocked = state.get("guardrails_blocked", False)
        
        # Use Rules Engine if available
        if self._rules_engine._loaded:
            return await self._execute_with_rules_engine(
                analysis, current_state, attempt_count, escalation_decision, safety_violation, sentiment, guardrails_blocked
            )
        else:
            # Fallback to legacy Python-based logic
            return await self._execute_legacy(
                analysis, current_state, attempt_count, escalation_decision, safety_violation, sentiment, guardrails_blocked
            )
    
    async def _execute_with_rules_engine(
        self,
        analysis: Dict[str, Any],
        current_state: str,
        attempt_count: int,
        escalation_decision: str,
        safety_violation: bool,
        sentiment: Dict[str, Any],
        guardrails_blocked: bool
    ) -> Dict[str, Any]:
        """Execute using declarative Rules Engine."""
        
        # 0. Blocked Check (Highest Priority)
        if guardrails_blocked:
             return {
                "dialog_state": BLOCKED,
                "attempt_count": attempt_count,
                 # "block" action implies we stop here or ensure routing doesn't go to generation.
                 # We set action_recommendation to "block" which routing understands as "end here".
                "action_recommendation": "block",
                "escalation_reason": "guardrails_block",
                "transition_source": "guardrails"
            }

        # 0.1. Phase 5: Safety Check (Second Highest Priority)
        if safety_violation:
            state_behavior = self._rules_engine.get_state_behavior(SAFETY_VIOLATION)
            return {
                "dialog_state": SAFETY_VIOLATION,
                "attempt_count": attempt_count,
                "state_behavior": state_behavior,
                "action_recommendation": state_behavior.get("action", "handoff"),
                "escalation_reason": state_behavior.get("escalation_reason", "safety_violation"),
                "transition_source": "safety_violation"
            }

        new_state = current_state
        new_attempt_count = attempt_count
        rule_matched = None
        
        # 1. Critical Override - explicit escalation from routing node
        if escalation_decision == "escalate":
            if analysis.get("escalation_requested"):
                new_state = ESCALATION_REQUESTED
            else:
                new_state = ESCALATION_NEEDED
            
            state_behavior = self._rules_engine.get_state_behavior(new_state)
            return {
                "dialog_state": new_state,
                "attempt_count": attempt_count,
                "state_behavior": state_behavior,
                "action_recommendation": state_behavior.get("action", "handoff"),
                "escalation_reason": state_behavior.get("escalation_reason", "escalation_override"),
                "transition_source": "escalation_override"
            }
        
        # Add confidence check to analysis signals
        confidence = analysis.get("confidence", 1.0)
        threshold = analysis.get("confidence_threshold", 0.3)
        analysis["confidence_below_threshold"] = confidence < threshold
        
        # 2. Evaluate rules
        result, new_attempt_count = self._rules_engine.evaluate(
            analysis=analysis,
            current_state=current_state,
            attempt_count=attempt_count
        )
        
        if result and result.matched:
            new_state = result.new_state
            rule_matched = result.rule_name
        
        # 3. Phase 5: Empathy Check (Post-processing)
        # If the determined state is a standard answer state, check if we need to enforce empathy
        if new_state in [ANSWER_PROVIDED, INITIAL] and sentiment.get("label") == "negative":
             return {
                "dialog_state": EMPATHY_MODE,
                "attempt_count": new_attempt_count,
                "state_behavior": self._rules_engine.get_state_behavior(EMPATHY_MODE),
                "action_recommendation": "auto_reply",
                "transition_source": "sentiment_empathy"
            }

        # 4. Get state behavior for prompt routing
        state_behavior = self._rules_engine.get_state_behavior(new_state)
        
        # 5. Extract action recommendation and escalation reason from state behavior
        action_recommendation = state_behavior.get("action", "auto_reply")
        escalation_reason = None
        
        if action_recommendation == "handoff":
            # Get escalation reason from state behavior or determine from signals
            escalation_reason = state_behavior.get("escalation_reason")
            if not escalation_reason:
                # Fallback logic
                if safety_violation:
                    escalation_reason = "safety_violation"
                elif analysis.get("escalation_requested"):
                    escalation_reason = "user_requested"
                elif analysis.get("confidence_below_threshold"):
                    escalation_reason = "low_confidence"
                else:
                    escalation_reason = "state_machine_decision"
        
        return {
            "dialog_state": new_state,
            "attempt_count": new_attempt_count,
            "state_behavior": state_behavior,
            "action_recommendation": action_recommendation,
            "escalation_reason": escalation_reason,
            "transition_source": rule_matched or "no_match"
        }
    
    async def _execute_legacy(
        self,
        analysis: Dict[str, Any],
        current_state: str,
        attempt_count: int,
        escalation_decision: str,
        safety_violation: bool,
        sentiment: Dict[str, Any],
        guardrails_blocked: bool
    ) -> Dict[str, Any]:
        """
        Legacy execution using Python-based rules.
        Fallback when rules.yaml is not available.
        """
        if guardrails_blocked:
             return {
                "dialog_state": BLOCKED,
                "attempt_count": attempt_count,
                "action_recommendation": "block",
                "escalation_reason": "guardrails_block"
            }

        # 0. Safety Check
        if safety_violation:
            return {
                "dialog_state": SAFETY_VIOLATION,
                "attempt_count": attempt_count,
                "action_recommendation": "handoff",
                "escalation_reason": "safety_violation"
            }

        new_state = current_state
        
        # 1. Critical Override
        if escalation_decision == "escalate":
            if analysis.get("escalation_requested"):
                return {
                    "dialog_state": ESCALATION_REQUESTED,
                    "attempt_count": attempt_count,
                    "action_recommendation": "handoff",
                    "escalation_reason": "user_requested"
                }
            else:
                return {
                    "dialog_state": ESCALATION_NEEDED,
                    "attempt_count": attempt_count,
                    "action_recommendation": "handoff",
                    "escalation_reason": "escalation_override"
                }

        # 2. Rule-Based Match
        rule_matched_state = None
        sorted_rules = sorted(TRANSITION_RULES, key=lambda x: x["priority"])
        
        for rule in sorted_rules:
            field = rule["condition_field"]
            value = rule["condition_value"]
            target = rule["target_state"]
            
            if analysis.get(field) == value:
                rule_matched_state = target
                break
                
        if rule_matched_state:
            if rule_matched_state == ANSWER_PROVIDED:
                if current_state == "RESOLVED":
                    attempt_count = 1
                else:
                    attempt_count += 1
            new_state = rule_matched_state

        params = get_node_params("state_machine")
        max_attempts = params.get("max_attempts_before_handoff", 3)

        # 3. Dynamic logic
        if new_state == ANSWER_PROVIDED and attempt_count > max_attempts:
            new_state = ESCALATION_NEEDED
            
        # 4. Phase 5: Empathy Check
        if new_state in [ANSWER_PROVIDED, INITIAL] and sentiment.get("label") == "negative":
             new_state = EMPATHY_MODE
        
        # 5. Check confidence (added for completeness)
        confidence = analysis.get("confidence", 1.0)
        threshold = analysis.get("confidence_threshold", 0.3)
        if confidence < threshold:
            new_state = ESCALATION_NEEDED

        # Determine action recommendation based on state
        action_recommendation = "auto_reply"
        escalation_reason = None
        
        if new_state in [ESCALATION_REQUESTED, ESCALATION_NEEDED, SAFETY_VIOLATION]:
            action_recommendation = "handoff"
            if new_state == SAFETY_VIOLATION:
                escalation_reason = "safety_violation"
            elif new_state == ESCALATION_REQUESTED:
                escalation_reason = "user_requested"
            elif confidence < threshold:
                escalation_reason = "low_confidence"
            else:
                escalation_reason = "repeated_failures"

        return {
            "dialog_state": new_state,
            "attempt_count": attempt_count,
            "action_recommendation": action_recommendation,
            "escalation_reason": escalation_reason
        }
    
    def get_state_behavior(self, state: str) -> Dict[str, Any]:
        """Get behavior configuration for a state (utility method)."""
        return self._rules_engine.get_state_behavior(state)


# For backward compatibility
state_machine_node = StateMachineNode()

