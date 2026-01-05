from typing import Dict, Any
from app.nodes.query_translation.metrics.translation_success_rate import TranslationSuccessRate
from app.nodes.query_translation.metrics.translation_required_rate import TranslationRequiredRate
from app.nodes.query_translation.metrics.query_modification_rate import QueryModificationRate

class QueryTranslationMetrics:
    """Агрегатор метрик для ноды перевода."""
    
    def __init__(self):
        self.success_metric = TranslationSuccessRate()
        self.required_metric = TranslationRequiredRate()
        self.modification_metric = QueryModificationRate()
    
    def calculate(self, evaluation: Dict[str, Any]) -> Dict[str, float]:
        return {
            "translation_required_rate": self.required_metric.calculate(evaluation),
            "translation_success_rate": self.success_metric.calculate(evaluation),
            "query_modification_rate": self.modification_metric.calculate(evaluation)
        }

translation_metrics = QueryTranslationMetrics()
