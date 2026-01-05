"""
Metrics for Output Guardrails Node
"""
from typing import Dict, Any, List
from app.nodes.base_node.metrics.base_metric import BaseMetric


class OutputGuardrailsMetric(BaseMetric):
    """Track output validation metrics"""
    
    def calculate(self, expected: Any, actual: Any, **kwargs) -> Any:
        """Calculate metric"""
        return 1.0 if expected == actual else 0.0
    
    def __init__(self):
        super().__init__()
        
        self.total_responses = 0
        self.blocked_responses = 0
        self.sanitized_responses = 0
        self.safe_responses = 0
        
        self.scanner_triggers = {
            "data_leakage": 0,
            "relevance": 0,
            "hallucination": 0,
            "refusal": 0,
            "toxicity": 0
        }
    
    def record(self, state: Dict[str, Any]):
        """Record metrics from state"""
        self.total_responses += 1
        
        if state.get("output_guardrails_blocked"):
            self.blocked_responses += 1
        elif state.get("output_guardrails_sanitized"):
            self.sanitized_responses += 1
        else:
            self.safe_responses += 1
        
        # Record triggers
        triggers = state.get("output_triggers", [])
        for trigger in triggers:
            if trigger in self.scanner_triggers:
                self.scanner_triggers[trigger] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        if self.total_responses == 0:
            return {"total_responses": 0}
        
        return {
            "total_responses": self.total_responses,
            "blocked_rate": self.blocked_responses / self.total_responses,
            "sanitized_rate": self.sanitized_responses / self.total_responses,
            "safe_rate": self.safe_responses / self.total_responses,
            "scanner_triggers": self.scanner_triggers
        }
