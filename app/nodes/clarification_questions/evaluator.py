from typing import Dict, Any, List, Optional
from app.nodes.base_node import BaseEvaluator

from .metrics import ClarificationCompleteness

class ClarificationQuestionsEvaluator(BaseEvaluator):
    """
    Evaluator for ClarificationQuestionsNode.
    Tracks clarification requests and completion rates.
    """
    
    def calculate_metrics(self, **kwargs) -> Dict[str, float]:
        completeness = ClarificationCompleteness()
        
        # kwargs usually contains 'output', 'ground_truth', 'input'
        output = kwargs.get("output", {})
        
        return {
            "clarification_completeness": completeness.calculate(output)
        }

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        return {}

evaluator = ClarificationQuestionsEvaluator()
