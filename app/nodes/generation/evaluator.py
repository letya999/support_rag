from typing import Dict, Any, Optional
from app.nodes.generation.metrics import Faithfulness, Relevancy

class GenerationEvaluator:
    def __init__(self):
        self.metrics = [Faithfulness(), Relevancy()]
        
    async def evaluate_batch(self, run_name: Optional[str] = None):
        # Placeholder for generation evaluation
        # Logic to evaluate generation using dataset
        pass

evaluator = GenerationEvaluator()
