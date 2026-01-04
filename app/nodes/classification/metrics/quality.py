from typing import List, Dict, Any
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from app.nodes.classification.metrics.base import ClassificationBaseMetric

class QualityMetrics(ClassificationBaseMetric):
    """
    Standard classification quality metrics (Accuracy, F1, Precision, Recall).
    """
    def calculate(self, y_true: List[str], y_pred: List[str], **kwargs) -> Dict[str, float]:
        if not y_true or not y_pred:
            return {}
            
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "f1_weighted": float(f1_score(y_true, y_pred, average='weighted', zero_division=0)),
            "precision_weighted": float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
            "recall_weighted": float(recall_score(y_true, y_pred, average='weighted', zero_division=0))
        }
