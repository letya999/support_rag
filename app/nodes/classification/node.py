from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.classification.classifier import ClassificationService

from app.observability.tracing import observe

class ClassificationNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("aggregated_query") or state.get("question", "")
        service = ClassificationService()
        
        result = await service.classify(question)
        
        return {
            "intent": result.intent,
            "intent_confidence": result.intent_confidence,
            "category": result.category,
            "category_confidence": result.category_confidence
        }

# For backward compatibility
classify_node = ClassificationNode()
