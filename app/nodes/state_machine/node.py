from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.nodes.state_machine.states_config import TRANSITION_RULES, STATE_CONFIG, INITIAL, ANSWER_PROVIDED, ESCALATION_NEEDED, ESCALATION_REQUESTED

class StateMachineNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main State Machine logic.
        """
        # Inputs
        analysis = state.get("dialog_analysis", {})
        current_state = state.get("dialog_state", INITIAL)
        attempt_count = state.get("attempt_count", 0)
        escalation_decision = state.get("escalation_decision", "auto_reply")
        
        if current_state is None:
            current_state = INITIAL
        if attempt_count is None:
            attempt_count = 0
        
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

        # 3. Dynamic logic
        if new_state == ANSWER_PROVIDED and attempt_count > STATE_CONFIG["max_attempts"]:
            if STATE_CONFIG["escalate_on_max_attempts"]:
                new_state = ESCALATION_NEEDED

        return {
            "dialog_state": new_state,
            "attempt_count": attempt_count
        }

# For backward compatibility
state_machine_node = StateMachineNode()
