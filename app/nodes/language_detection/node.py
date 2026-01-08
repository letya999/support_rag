from typing import Dict, Any, Optional
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.services.config_loader.loader import get_node_params

try:
    from langdetect import detect, detect_langs
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

class LanguageDetectionNode(BaseNode):
    """
    Detects language of user query.
    
    Contracts:
        Input:
            Required:
                - question (str): User's question text
            Optional: None
        
        Output:
            Guaranteed:
                - detected_language (str): ISO language code (en, ru, etc.)
                - language_confidence (float): Detection confidence 0.0-1.0
            Conditional: None
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": []
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["detected_language", "language_confidence"],
        "conditional": []
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute language detection."""
        params = get_node_params("language_detection")
        fallback_lang = params.get("fallback_language", "ru")
        use_heuristic = params.get("use_fallback_heuristic", True)
        
        question = state.get("question", "")
        if not question:
            return {
                "detected_language": fallback_lang, 
                "language_confidence": 0.0
            }

        try:
            if LANGDETECT_AVAILABLE:
                detected = detect_langs(question)
                primary_lang = detected[0]
                return {
                    "detected_language": primary_lang.lang,
                    "language_confidence": round(primary_lang.prob, 2)
                }
            else:
                 # Simple heuristic as fallback: check if cyrillic characters exist
                 if use_heuristic:
                     has_cyrillic = any('а' <= char.lower() <= 'я' for char in question)
                     return {
                        "detected_language": "ru" if has_cyrillic else "en",
                        "language_confidence": 0.5
                    }
                 return {
                    "detected_language": fallback_lang,
                    "language_confidence": 0.5
                 }
        except Exception:
             return {
                "detected_language": fallback_lang,  # fallback
                "language_confidence": 0.5
            }

# Export singleton
language_detection_node = LanguageDetectionNode()

