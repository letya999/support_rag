from typing import List, Dict, Any
from collections import Counter

class PromptRoutingEvaluator:
    """
    Evaluator for prompt routing performance.
    Since we might not have ground truth for 'correct prompt' in the dataset,
    this primarily tracks distribution and potential mismatches if we infer logic.
    """
    
    def calculate_metrics(self, ground_truth: List[str], predictions: List[str]) -> Dict[str, float]:
        """
        Calculate accuracy if ground truth is available.
        Otherwise this logic might need custom implementation per use case.
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

evaluator = PromptRoutingEvaluator()
