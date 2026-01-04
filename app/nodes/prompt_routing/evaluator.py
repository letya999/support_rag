from typing import List, Dict, Any, Optional
from collections import Counter
from app.nodes.base_node import BaseEvaluator

class PromptRoutingEvaluator(BaseEvaluator):
    """
    Evaluator for prompt routing performance.
    """
    
    def calculate_metrics(self, ground_truth: List[str], predictions: List[str], **kwargs) -> Dict[str, float]:
        """
        Calculate accuracy if ground truth is available.
        """
        if not ground_truth or not predictions:
            return {"accuracy": 0.0}
            
        correct = 0
        for gt, pred in zip(ground_truth, predictions):
            if gt == pred:
                correct += 1
                
        return {
            "accuracy": correct / len(ground_truth)
        }
    
    def analyze_distribution(self, selected_prompts: List[str]) -> Dict[str, float]:
        """
        Returns the percentage distribution of selected prompts.
        """
        if not selected_prompts:
            return {}
            
        total = len(selected_prompts)
        counts = Counter(selected_prompts)
        
        return {k: v / total for k, v in counts.items()}

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        return {}

# For backward compatibility
evaluator = PromptRoutingEvaluator()
