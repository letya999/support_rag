"""
Query Translation Node

Переводит запрос пользователя на язык документов в БД для унифицированного поиска.
Это критически важно для:
- Векторного поиска (embeddings работают лучше в пределах одного языка)
- Лексического поиска (требуется точное совпадение языка с документами)
"""
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.services.config_loader.loader import get_global_param

class QueryTranslationNode(BaseNode):
    """
    Translates user query to document language for unified search.
    
    Critical for:
    - Vector search (embeddings work better within one language)
    - Lexical search (requires exact language match with documents)
    
    Contracts:
        Input:
            Required:
                - question (str): Original user question
            Optional:
                - detected_language (str): Detected language of question
                - language_confidence (float): Confidence of detection
                - aggregated_query (str): Pre-processed query
        
        Output:
            Guaranteed:
                - translated_query (str): Translated query (or original if no translation needed)
            Conditional:
                - translation_performed (bool): Whether translation was done
                - source_language (str): Original language
                - target_language (str): Target language
                - translation_error (str): Error message if failed
    """
    
    INPUT_CONTRACT = {
        "required": ["question"],
        "optional": ["detected_language", "language_confidence", "aggregated_query"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["translated_query"],
        "conditional": [
            "translation_performed",
            "source_language",
            "target_language",
            "translation_error"
        ]
    }
    
    def __init__(self, name: str = "query_translation"):
        super().__init__(name)
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate query to document language if needed.
        """
        from app.nodes.query_translation.translator import translator
        from app.services.config_loader.loader import get_node_params
        
        # Получаем параметры именно этой ноды
        # ВАЖНО: get_node_params возвращает уже смерженный плоский dict (parameters + config)
        node_params = get_node_params(self.name)
        
        # Фильтрация по уверенности детекции
        min_conf = node_params.get("min_detection_confidence", 0.0)
        actual_conf = state.get("language_confidence", 1.0)
        
        # Язык документов: сначала из конфига ноды, потом из глобального
        # node_params уже содержит document_language на верхнем уровне
        document_language = node_params.get("document_language") or get_global_param("default_language", "en")
        
        query = state.get("aggregated_query") or state.get("question", "")
        detected_language = state.get("detected_language", "en")
        
        if not query:
            return {"translated_query": query}

        if actual_conf < min_conf:
            print(f"⚠️ Low language detection confidence ({actual_conf} < {min_conf}), using original query")
            return {"translated_query": query, "translation_performed": False}
        
        # Skip translation if already in target language
        if detected_language == document_language:
            print(f"✅ Query already in document language ({document_language}), skipping translation")
            return {
                "translated_query": query
            }
        
        # Translate
        try:
            print(f"🔄 Translating query from '{detected_language}' to '{document_language}'")
            translated_query = translator.translate_query(query, target_lang=document_language)
            print(f"✅ Translation successful: '{query}' → '{translated_query}'")
            
            return {
                "translated_query": translated_query,
                "translation_performed": True,
                "source_language": detected_language,
                "target_language": document_language
            }
        except Exception as e:
            print(f"⚠️ Translation failed: {e}, using original query")
            return {
                "translated_query": query,
                "translation_performed": False,
                "translation_error": str(e)
            }

# Export singleton
query_translation_node = QueryTranslationNode()
