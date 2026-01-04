from typing import List, Dict, Any, Optional
from app.nodes.base_node import BaseEvaluator
from app.nodes.easy_classification.metrics.quality import QualityMetrics
from app.nodes.easy_classification.metrics.calibration import CalibrationMetrics

class EasyClassificationEvaluator(BaseEvaluator):
    def __init__(self):
        self.quality = QualityMetrics()
        self.calibration = CalibrationMetrics()

    def calculate_metrics(
        self, 
        y_true: List[str], 
        y_pred: List[str], 
        confidences: Optional[List[float]] = None,
        **kwargs
    ) -> Dict[str, float]:
        """
        Calculate classification metrics.
        """
        results = self.quality.calculate(y_true, y_pred)
        
        if confidences:
            correct_flags = [t == p for t, p in zip(y_true, y_pred)]
            gap = self.calibration.calculate_gap(confidences, correct_flags)
            results["confidence_gap"] = gap
            
        return results

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        return {}

evaluator = EasyClassificationEvaluator()
