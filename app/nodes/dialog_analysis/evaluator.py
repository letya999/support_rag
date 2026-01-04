from typing import List, Dict, Any, Optional
from app.nodes.base_node import BaseEvaluator

class DialogEvaluator(BaseEvaluator):
    def calculate_metrics(
        self, 
        y_true: List[Dict[str, Any]], 
        y_pred: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, float]:
        """
        Calculate metrics for dialog analysis.
        Expects lists of dictionaries containing keys: 
        'is_gratitude', 'escalation_requested', 'frustration_detected', etc.
        """
        metrics = {}
        keys = ["is_gratitude", "escalation_requested", "is_question", "frustration_detected", "repeated_question"]
        
        for key in keys:
            correct = 0
            total = len(y_true)
            
            if total == 0:
                metrics[f"{key}_accuracy"] = 0.0
                continue
                
            for t, p in zip(y_true, y_pred):
                # Treat missing keys as False
                val_true = t.get(key, False)
                val_pred = p.get(key, False)
                if val_true == val_pred:
                    correct += 1
            
            metrics[f"{key}_accuracy"] = correct / total
            
        return metrics

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        return {}

evaluator = DialogEvaluator()
