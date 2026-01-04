from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

class BaseEvaluator(ABC):
    """
    Base class for node evaluators.
    Provides common patterns for running single and batch evaluations.
    """
    
    def __init__(self):
        self.metrics = []

    @abstractmethod
    def calculate_metrics(self, **kwargs) -> Dict[str, float]:
        """
        Calculate metrics for given inputs/outputs.
        
        Args:
            **kwargs: Metrics-specific inputs (e.g. expected, actual, context)
        """
        pass

    @abstractmethod
    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        """
        Run the node on one item and calculate metrics.
        """
        pass

    async def evaluate_batch(
        self, 
        items: List[Any], 
        run_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run batch evaluation loop.
        """
        if not run_name:
            run_name = f"{self.__class__.__name__}-{datetime.now().strftime('%Y%m%d-%H%M')}"
            
        results = []
        return {
            "run_name": run_name,
            "results": results,
            "metrics": {}
        }
