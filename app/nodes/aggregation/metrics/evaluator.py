from typing import Dict, Any, List

class AggregationEvaluator:
    """
    Simple evaluator for aggregation logic.
    Since we often lack ground truth for 'ideal rewritten query', 
    we measure proxy metrics like 'expansion_ratio' or 'entity_count'.
    """
    
    def calculate_metrics(self, original_question: str, aggregated_query: str, extracted_entities: Dict[str, List[str]]) -> Dict[str, float]:
        metrics = {}
        
        # 1. Is Aggregated? (Boolean-like score)
        metrics["is_aggregated"] = 1.0 if original_question != aggregated_query else 0.0
        
        # 2. Entity Count
        total_entities = sum(len(v) for v in extracted_entities.values())
        metrics["entity_count"] = float(total_entities)
        
        # 3. Expansion Ratio (Length increase)
        orig_len = len(original_question)
        agg_len = len(aggregated_query)
        if orig_len > 0:
            metrics["expansion_ratio"] = agg_len / orig_len
        else:
            metrics["expansion_ratio"] = 1.0
            
        return metrics

evaluator = AggregationEvaluator()
