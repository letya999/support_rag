from typing import List, Any, Dict
from app.nodes.base_node import BaseEvaluator

def calculate_mrr(relevant_indices: List[int]) -> float:
    """
    Calculate Mean Reciprocal Rank.
    relevant_indices: 1-based indices of relevant documents in the ranked list.
    """
    if not relevant_indices:
        return 0.0
    
    # MRR is 1/rank of the first relevant document
    first_rank = min(relevant_indices)
    return 1.0 / first_rank

def calculate_precision_at_k(relevant_indices: List[int], k: int) -> float:
    """
    Calculate Precision@k.
    relevant_indices: 1-based indices of relevant documents.
    """
    if k <= 0:
        return 0.0
        
    relevant_count = len([idx for idx in relevant_indices if idx <= k])
    return relevant_count / k

class RerankEvaluator(BaseEvaluator):
    def __init__(self, k: int = 5):
        super().__init__()
        self.k = k

    def calculate_metrics(self, reranked_docs: List[str], ground_truth: str, **kwargs) -> Dict[str, float]:
        """
        Evaluate reranking results against ground truth.
        """
        # Very simple relevance check: is ground truth content in the doc?
        relevant_indices = []
        for i, doc in enumerate(reranked_docs):
            if ground_truth.strip() in doc or doc in ground_truth:
                relevant_indices.append(i + 1)
        
        mrr = calculate_mrr(relevant_indices)
        precision_k = calculate_precision_at_k(relevant_indices, self.k)
        
        return {
            "mrr": mrr,
            f"precision_at_{self.k}": precision_k
        }

    async def evaluate_single(self, **kwargs) -> Dict[str, Any]:
        return {}

# For backward compatibility
evaluator = RerankEvaluator()
