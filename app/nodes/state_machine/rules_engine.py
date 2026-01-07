"""
Rules Engine for State Machine.

Loads declarative rules from rules.yaml and evaluates them against
dialog analysis signals to determine state transitions.
"""

import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import yaml


RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")


@dataclass
class TransitionResult:
    """Result of rule evaluation."""
    new_state: str
    rule_name: str
    rule_description: str
    actions: List[Dict[str, Any]]
    matched: bool = True


class RulesEngine:
    """
    Rules Engine for State Machine transitions.
    
    Loads rules from YAML and evaluates them against dialog analysis signals.
    Supports:
    - Priority-based rule evaluation
    - Multiple condition operators (equals, not_equals, gt, lt, in)
    - Actions (log, reset_attempt_count, increment_attempts)
    - Dynamic rules (based on attempt count, etc.)
    """
    
    _instance: Optional['RulesEngine'] = None
    _rules: List[Dict[str, Any]] = []
    _dynamic_rules: List[Dict[str, Any]] = []
    _defaults: Dict[str, Any] = {}
    _state_behaviors: Dict[str, Dict[str, Any]] = {}
    _loaded: bool = False
    
    def __new__(cls) -> 'RulesEngine':
        if cls._instance is None:
            cls._instance = super(RulesEngine, cls).__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not self._loaded:
            self._load_rules()
    
    def _load_rules(self) -> bool:
        """Load rules from YAML file."""
        if not os.path.exists(RULES_PATH):
            print(f"[RulesEngine] Warning: rules.yaml not found at {RULES_PATH}")
            return False
        
        try:
            with open(RULES_PATH, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            self._rules = data.get('rules', [])
            self._dynamic_rules = data.get('dynamic_rules', [])
            self._defaults = data.get('defaults', {})
            self._state_behaviors = data.get('state_behaviors', {})
            
            # Sort rules by priority
            self._rules = sorted(self._rules, key=lambda x: x.get('priority', 100))
            
            self._loaded = True
            print(f"[RulesEngine] Loaded {len(self._rules)} rules, {len(self._dynamic_rules)} dynamic rules")
            return True
            
        except Exception as e:
            print(f"[RulesEngine] Error loading rules: {e}")
            return False
    
    def reload(self) -> bool:
        """Force reload rules from file."""
        self._loaded = False
        return self._load_rules()
    
    @property
    def defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return self._defaults.copy()
    
    def get_initial_state(self) -> str:
        """Get the configured initial state."""
        return self._defaults.get('initial_state', 'INITIAL')
    
    def get_max_attempts(self) -> int:
        """Get max attempts before escalation."""
        return self._defaults.get('max_attempts_before_escalation', 3)
    
    def get_state_behavior(self, state: str) -> Dict[str, Any]:
        """Get behavior configuration for a state (for prompt routing)."""
        return self._state_behaviors.get(state, {
            'tone': 'professional',
            'action': 'auto_reply',
            'prompt_hint': 'standard'
        })
    
    def _check_condition(
        self, 
        condition: Dict[str, Any], 
        analysis: Dict[str, Any]
    ) -> bool:
        """
        Check if a condition matches the analysis data.
        
        Supports operators: equals, not_equals, gt, lt, gte, lte, in, not_in, exists
        """
        field = condition.get('field')
        operator = condition.get('operator', 'equals')
        expected = condition.get('value')
        
        actual = analysis.get(field)
        
        if operator == 'equals':
            return actual == expected
        elif operator == 'not_equals':
            return actual != expected
        elif operator == 'gt':
            return actual is not None and actual > expected
        elif operator == 'lt':
            return actual is not None and actual < expected
        elif operator == 'gte':
            return actual is not None and actual >= expected
        elif operator == 'lte':
            return actual is not None and actual <= expected
        elif operator == 'in':
            return actual in expected if isinstance(expected, list) else False
        elif operator == 'not_in':
            return actual not in expected if isinstance(expected, list) else True
        elif operator == 'exists':
            return (actual is not None) == expected
        else:
            return False
    
    def evaluate(
        self, 
        analysis: Dict[str, Any],
        current_state: str,
        attempt_count: int = 0
    ) -> Tuple[Optional[TransitionResult], int]:
        """
        Evaluate rules against dialog analysis.
        
        Args:
            analysis: Dialog analysis signals
            current_state: Current state
            attempt_count: Current attempt count
            
        Returns:
            Tuple of (TransitionResult or None, updated attempt_count)
        """
        new_attempt_count = attempt_count
        
        # 1. Check static rules in priority order
        for rule in self._rules:
            condition = rule.get('condition', {})
            
            # Check attempt count constraints if specified
            requires_attempts_lt = rule.get('requires_attempts_less_than')
            requires_attempts_gte = rule.get('requires_attempts_gte')
            
            if requires_attempts_lt is not None and attempt_count >= requires_attempts_lt:
                # Skip this rule if attempts >= threshold
                continue
            
            if requires_attempts_gte is not None and attempt_count < requires_attempts_gte:
                # Skip this rule if attempts < threshold
                continue
            
            if self._check_condition(condition, analysis):
                # Rule matched!
                result = TransitionResult(
                    new_state=rule.get('target_state', current_state),
                    rule_name=rule.get('name', 'unknown'),
                    rule_description=rule.get('description', ''),
                    actions=rule.get('actions', [])
                )
                
                # Process actions
                for action in result.actions:
                    action_type = action.get('type')
                    if action_type == 'reset_attempt_count':
                        new_attempt_count = 0
                    elif action_type == 'increment_attempts':
                        new_attempt_count += 1
                    elif action_type == 'log':
                        # Could be used for observability
                        pass
                
                # Check post_condition if exists
                post_condition = rule.get('post_condition', {})
                if post_condition:
                    if_attempts_exceed = post_condition.get('if_attempts_exceed')
                    override_state = post_condition.get('override_state')
                    
                    if if_attempts_exceed is not None and new_attempt_count > if_attempts_exceed and override_state:
                        # Override the target state based on attempt count
                        result.new_state = override_state
                
                return result, new_attempt_count
        
        # 2. Check dynamic rules
        for dyn_rule in self._dynamic_rules:
            cond_type = dyn_rule.get('condition', {}).get('type')
            requires_state = dyn_rule.get('requires_current_state')
            
            # Check state requirement
            if requires_state and current_state != requires_state:
                continue
            
            if cond_type == 'attempts_exceeded':
                threshold_key = dyn_rule.get('condition', {}).get('threshold_from_config')
                threshold = self._defaults.get(threshold_key, 3)
                
                if new_attempt_count > threshold:
                    return TransitionResult(
                        new_state=dyn_rule.get('target_state', current_state),
                        rule_name=dyn_rule.get('name', 'dynamic'),
                        rule_description=dyn_rule.get('description', ''),
                        actions=[]
                    ), new_attempt_count
        
        # 3. No rule matched - keep current state
        return None, new_attempt_count
    
    def get_all_states(self) -> List[str]:
        """Get list of all defined states."""
        return list(self._state_behaviors.keys())


# Convenience functions
def get_rules_engine() -> RulesEngine:
    """Get singleton RulesEngine instance."""
    return RulesEngine()
