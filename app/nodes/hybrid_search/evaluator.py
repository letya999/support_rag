from typing import List, Dict, Any, Optional
from app.nodes.base_node import BaseEvaluator

class HybridSearchEvaluator(BaseEvaluator):
    def calculate_metrics(self, **kwargs) -> Dict[str, float]:
        return {}

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        return {}

evaluator = HybridSearchEvaluator()
