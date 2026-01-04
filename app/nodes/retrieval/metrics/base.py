from abc import abstractmethod
from typing import Any, List
from app.nodes.base_node.metrics.base_metric import BaseMetric

class RetrievalBaseMetric(BaseMetric):
    """Base class for all retrieval metrics."""
    
    @abstractmethod
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        """Calculate metric for a single item."""
        pass
