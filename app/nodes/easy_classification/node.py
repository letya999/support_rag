import time
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.services.classification.semantic_service import SemanticClassificationService
from app.observability.tracing import observe
from app.services.config_loader.loader import get_node_params

class SemanticClassificationNode(BaseNode):
    """
    Classifies user query using semantic classification.
    
    Contracts:
        Input:
            Required: None
            Optional:
                - question (str): User question
                - translated_query (str): Translated query
                - aggregated_query (str): Enhanced query
        
        Output:
            Guaranteed:
                - semantic_intent (str): Detected intent
                - semantic_category (str): Detected category
                - semantic_time (float): Classification time
            Conditional:
                - semantic_intent_confidence (float): Intent confidence
                - semantic_category_confidence (float): Category confidence
    """
    
    INPUT_CONTRACT = {
        "required": [],
        "optional": ["question", "translated_query", "aggregated_query"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["semantic_intent", "semantic_category", "semantic_time"],
        "conditional": ["semantic_intent_confidence", "semantic_category_confidence"]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Use translated_query if available (from query_translation node)
        # This ensures classification happens in document language
        question = state.get("translated_query") or state.get("aggregated_query") or state.get("question", "")
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
