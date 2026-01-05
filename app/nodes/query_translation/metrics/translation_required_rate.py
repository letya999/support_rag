from typing import Dict, Any

class TranslationRequiredRate:
    """Частота запросов, требующих перевода (язык пользователя != язык документов)."""
    
    def calculate(self, evaluation: Dict[str, Any]) -> float:
        return 1.0 if evaluation.get("translation_required") else 0.0
