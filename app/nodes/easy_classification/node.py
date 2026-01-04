import time
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.easy_classification.semantic_classifier import SemanticClassificationService
from app.observability.tracing import observe

class SemanticClassificationNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("aggregated_query") or state.get("question", "")
        service = SemanticClassificationService()
        
        start_time = time.time()
        result = await service.classify(question)
        end_time = time.time()
        
        if result is None:
            return {
                "semantic_intent": "error",
                "semantic_category": "error",
                "semantic_time": end_time - start_time
            }
        
        return {
            "semantic_intent": result.intent,
            "semantic_intent_confidence": result.intent_confidence,
            "semantic_category": result.category,
            "semantic_category_confidence": result.category_confidence,
            "semantic_time": end_time - start_time
        }

# For backward compatibility with graph definition (if any)
fasttext_classify_node = SemanticClassificationNode()
