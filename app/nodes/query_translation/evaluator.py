"""
Evaluator for Query Translation Node
"""
from typing import Dict, Any
from app.nodes.base_node import BaseEvaluator

class QueryTranslationEvaluator(BaseEvaluator):
    """Evaluates query translation quality and performance."""
    
    def __init__(self):
        super().__init__()
        from app.nodes.query_translation.metrics import translation_metrics
        self.metrics_calculator = translation_metrics

    def calculate_metrics(self, **kwargs) -> Dict[str, float]:
        """
        Calculate metrics for translation.
        Expects 'evaluation' in kwargs.
        """
        evaluation = kwargs.get("evaluation", {})
        return self.metrics_calculator.calculate(evaluation)

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        """
        Run the node on one item and calculate metrics.
        """
        # Placeholder for standalone evaluation if needed
        return {}
    
    def evaluate(self, state: Dict[str, Any], output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate translation results from a pipeline run.
        
        Metrics:
        - translation_required: Whether translation was needed
        - translation_success: Whether translation succeeded
        - translation_performed: Actual translation flag
        """
        detected_lang = state.get("detected_language", "unknown")
        translated_query = output.get("translated_query", "")
        original_query = state.get("aggregated_query") or state.get("question", "")
        translation_performed = output.get("translation_performed", False)
        translation_error = output.get("translation_error")
        
        # Check if translation was required
        from app.services.config_loader.loader import get_global_param
        document_language = get_global_param("default_language", "en") # English now default!
        translation_required = detected_lang != document_language
        
        # Translation success: if performed, it should have a result and no error
        # If not performed, success is True only if not required
        translation_success = False
        if translation_performed:
            translation_success = not translation_error
        else:
            translation_success = not translation_required
        
        # Query changed
        query_changed = translated_query != original_query
        
        return {
            "translation_required": translation_required,
            "translation_performed": translation_performed,
            "translation_success": translation_success,
            "query_changed": query_changed,
            "source_language": detected_lang,
            "target_language": document_language,
            "translation_error": translation_error
        }

# Export singleton
evaluator = QueryTranslationEvaluator()
