from abc import ABC, abstractmethod
from typing import Any, List

class BaseMetric(ABC):
    """
    Base class for all metrics (retrieval, generation, classification, etc.)
    """
    
    @abstractmethod
    def calculate(self, expected: Any, actual: Any, **kwargs) -> Any:
        """
        Calculate metric for a single item or a batch.
        """
        pass

    def aggregate(self, scores: List[float]) -> float:
        """
        Default aggregation: arithmetic mean.
        """
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
