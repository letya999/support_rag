from abc import ABC, abstractmethod
from typing import Any, List, Dict

class BaseMetric(ABC):
    """Base class for all retrieval metrics."""
    
    @abstractmethod
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """Calculate metric for a single item."""
        pass
        
    @abstractmethod
    def aggregate(self, scores: List[float]) -> float:
        """Aggregate scores across a batch."""
        pass
