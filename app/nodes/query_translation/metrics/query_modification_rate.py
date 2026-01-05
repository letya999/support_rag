from typing import Dict, Any

class QueryModificationRate:
    """Частота фактического изменения текста запроса после перевода."""
    
    def calculate(self, evaluation: Dict[str, Any]) -> float:
        return 1.0 if evaluation.get("query_changed") else 0.0
