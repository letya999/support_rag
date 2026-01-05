import time
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.easy_classification.semantic_classifier import SemanticClassificationService
from app.observability.tracing import observe
from app.services.config_loader.loader import get_node_params

class SemanticClassificationNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("aggregated_query") or state.get("question", "")
        service = SemanticClassificationService()
        
        params = get_node_params("easy_classification")
        i_threshold = params.get("intent_confidence_threshold", 0.3)
        c_threshold = params.get("category_confidence_threshold", 0.3)
        fallback_intent = params.get("fallback_intent", "unknown")
        fallback_category = params.get("fallback_category", "General")

        start_time = time.time()
        result = await service.classify(question)
        end_time = time.time()
        
        if result is None:
            return {
                "semantic_intent": fallback_intent,
                "semantic_category": fallback_category,
                "semantic_time": end_time - start_time
            }
        
        # Apply thresholds
        intent = result.intent if result.intent_confidence >= i_threshold else fallback_intent
        category = result.category if result.category_confidence >= c_threshold else fallback_category

        return {
            "semantic_intent": intent,
            "semantic_intent_confidence": result.intent_confidence,
            "semantic_category": category,
            "semantic_category_confidence": result.category_confidence,
            "semantic_time": end_time - start_time
        }

# For backward compatibility with graph definition (if any)
fasttext_classify_node = SemanticClassificationNode()
