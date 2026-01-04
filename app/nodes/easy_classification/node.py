import time
from app.pipeline.state import State
from app.nodes.easy_classification.fasttext_classifier import FastTextClassificationService

async def fasttext_classify_node(state: State) -> State:
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
