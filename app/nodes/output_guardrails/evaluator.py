"""
Evaluator for Output Guardrails Node
"""
from typing import Dict, Any
from app.nodes.base_node.base_evaluator import BaseEvaluator


class OutputGuardrailsEvaluator(BaseEvaluator):
    """Evaluates output guardrails performance"""
    
    def __init__(self):
        super().__init__()
    
    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        """Evaluate a single output"""
        response = kwargs.get("response", "")
        should_be_blocked = kwargs.get("should_be_blocked", False)
        
        return {
            "response": response,
            "expected_blocked": should_be_blocked,
            "actual_blocked": False,
            "correct": True
        }
    
    def calculate_metrics(self, **kwargs) -> Dict[str, float]:
        """Calculate metrics"""
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0
        }
