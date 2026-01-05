from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.services.config_loader.loader import get_node_params
from app.nodes.state_machine.rules_engine import get_rules_engine, RulesEngine
from app.nodes.state_machine.states_config import (
    TRANSITION_RULES, STATE_CONFIG, 
    INITIAL, ANSWER_PROVIDED, ESCALATION_NEEDED, ESCALATION_REQUESTED
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
        
        # Use Rules Engine if available
        if self._rules_engine._loaded:
            return await self._execute_with_rules_engine(
                analysis, current_state, attempt_count, escalation_decision
            )
        else:
            # Fallback to legacy Python-based logic
            return await self._execute_legacy(
                analysis, current_state, attempt_count, escalation_decision
            )
    
    async def _execute_with_rules_engine(
        self,
        analysis: Dict[str, Any],
        current_state: str,
        attempt_count: int,
        escalation_decision: str
    ) -> Dict[str, Any]:
        """Execute using declarative Rules Engine."""
        
        new_state = current_state
        new_attempt_count = attempt_count
        rule_matched = None
        
        # 1. Critical Override - explicit escalation from routing node
        if escalation_decision == "escalate":
            if analysis.get("escalation_requested"):
                new_state = ESCALATION_REQUESTED
            else:
                new_state = ESCALATION_NEEDED
            
            return {
                "dialog_state": new_state,
                "attempt_count": attempt_count,
                "state_behavior": self._rules_engine.get_state_behavior(new_state),
                "transition_source": "escalation_override"
            }
        
        # 2. Evaluate rules
        result, new_attempt_count = self._rules_engine.evaluate(
            analysis=analysis,
            current_state=current_state,
            attempt_count=attempt_count
        )
        
        if result and result.matched:
            new_state = result.new_state
            rule_matched = result.rule_name
        
        # 3. Get state behavior for prompt routing
        state_behavior = self._rules_engine.get_state_behavior(new_state)
        
        return {
            "dialog_state": new_state,
            "attempt_count": new_attempt_count,
            "state_behavior": state_behavior,
            "transition_source": rule_matched or "no_match"
        }
    
    async def _execute_legacy(
        self,
        analysis: Dict[str, Any],
        current_state: str,
        attempt_count: int,
        escalation_decision: str
    ) -> Dict[str, Any]:
        """
        Legacy execution using Python-based rules.
        Fallback when rules.yaml is not available.
        """
        new_state = current_state
        
        # 1. Critical Override
        if escalation_decision == "escalate":
            if analysis.get("escalation_requested"):
                return {
                    "dialog_state": ESCALATION_REQUESTED,
                    "attempt_count": attempt_count
                }
            else:
                return {
                    "dialog_state": ESCALATION_NEEDED,
                    "attempt_count": attempt_count
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

        return {
            "dialog_state": new_state,
            "attempt_count": attempt_count
        }
    
    def get_state_behavior(self, state: str) -> Dict[str, Any]:
        """Get behavior configuration for a state (utility method)."""
        return self._rules_engine.get_state_behavior(state)


# For backward compatibility
state_machine_node = StateMachineNode()

