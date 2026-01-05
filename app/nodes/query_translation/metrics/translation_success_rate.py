from typing import Dict, Any

class TranslationSuccessRate:
    """Процент успешно выполненных переводов от числа запрошенных."""
    
    def calculate(self, evaluation: Dict[str, Any]) -> float:
        if not evaluation.get("translation_required"):
            return 1.0  # Если перевод не требовался, считаем это "условным успехом"
            
        return 1.0 if evaluation.get("translation_success") else 0.0
