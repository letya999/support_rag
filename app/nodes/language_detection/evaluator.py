from typing import Dict, Any, List
from app.nodes.base_node.base_evaluator import BaseEvaluator
from app.nodes.language_detection.node import language_detection_node

class LanguageDetectionEvaluator(BaseEvaluator):
    def calculate_metrics(self, inputs: List[str], expected: List[str], actual: List[str]) -> Dict[str, float]:
        correct = sum(1 for a, e in zip(actual, expected) if a == e)
        accuracy = correct / len(expected) if expected else 0.0
        return {"accuracy": accuracy}
    
    async def evaluate_single(self, text: str, expected_lang: str) -> Dict[str, Any]:
        state = {"question": text}
        result = await language_detection_node.execute(state)
        detected = result.get("detected_language")
        
        return {
            "input": text,
            "expected": expected_lang,
            "actual": detected,
            "confidence": result.get("language_confidence"),
            "correct": detected == expected_lang
        }
