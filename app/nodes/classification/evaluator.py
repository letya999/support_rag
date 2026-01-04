from typing import List, Dict, Any, Optional
from app.nodes.base_node import BaseEvaluator
from app.nodes.classification.metrics.quality import QualityMetrics
from app.nodes.classification.metrics.calibration import CalibrationMetrics

class ClassificationEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__()
        self.quality = QualityMetrics()
        self.calibration = CalibrationMetrics()
        self.metrics = [self.quality, self.calibration]

    def calculate_metrics(
        self, 
        y_true: List[str], 
        y_pred: List[str], 
        confidences: Optional[List[float]] = None
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
        """
        Placeholder for specific classification evaluation logic.
        """
        return {}

evaluator = ClassificationEvaluator()
