import time
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.easy_classification.fasttext_classifier import FastTextClassificationService
from app.observability.tracing import observe

class FastTextClassificationNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("aggregated_query") or state.get("question", "")
        service = FastTextClassificationService()
        
        start_time = time.time()
        result = await service.classify(question)
        end_time = time.time()
        
        if result is None:
            return {
                "fasttext_intent": "error",
                "fasttext_category": "error",
                "fasttext_time": end_time - start_time
            }
        
        return {
            "fasttext_intent": result.intent,
            "fasttext_intent_confidence": result.intent_confidence,
            "fasttext_category": result.category,
            "fasttext_category_confidence": result.category_confidence,
            "fasttext_time": end_time - start_time
        }

# For backward compatibility
fasttext_classify_node = FastTextClassificationNode()
