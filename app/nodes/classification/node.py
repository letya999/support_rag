from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.classification.classifier import ClassificationService

from app.observability.tracing import observe

class ClassificationNode(BaseNode):
    """
    Classifies user query for intent and category.
    
    Contracts:
        Input:
            Required: None
            Optional:
                - question (str): User question
                - aggregated_query (str): Enhanced query
        
        Output:
            Guaranteed:
                - intent (str): Detected intent
                - category (str): Detected category
            Conditional:
                - intent_confidence (float): Intent confidence
                - category_confidence (float): Category confidence
    """
    
    INPUT_CONTRACT = {
        "required": [],
        "optional": ["question", "aggregated_query"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["intent", "category"],
        "conditional": ["intent_confidence", "category_confidence"]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute query classification.

        Args:
            state: Current pipeline state

        Returns:
            Dict: State updates with intent and category
        """
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
