from app.pipeline.state import State
from app.nodes.classification.classifier import ClassificationService

async def classify_node(state: State) -> State:
    question = state["question"]
    service = ClassificationService()
    
    result = await service.classify(question)
    
    return {
        "intent": result.intent,
        "intent_confidence": result.intent_confidence,
        "category": result.category,
        "category_confidence": result.category_confidence
    }
