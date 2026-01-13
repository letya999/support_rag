from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from app.logging_config import logger

from app.observability.langfuse_client import get_langfuse_client
from app.observability.score_logger import log_score
from app.observability.tracing import observe
from app.dataset.loader import load_ground_truth_dataset, sync_dataset_to_langfuse
from app.nodes.base_node import BaseEvaluator
from app.nodes.retrieval.search import retrieve_context
from app.nodes.retrieval.metrics import HitRate, MRR, ExactMatch, AverageScore, FirstChunkScore, Recall, F1Score
from app.nodes.reranking.metrics.ndcg import NDCG

class RetrievalEvaluator(BaseEvaluator):
    def __init__(self):
        self.metrics = [HitRate(), MRR(), ExactMatch(), AverageScore(), FirstChunkScore(), Recall(), F1Score(), NDCG()]

    def calculate_metrics(self, expected_answer: Union[str, List[str]], retrieved_docs: List[str], retrieved_scores: List[float], top_k: int = 3) -> Dict[str, float]:
        """
        Calculate metrics for key-value pairs of expected vs actual.
        """
        retrieved_chunks = [
            {"content": doc, "score": score} 
            for doc, score in zip(retrieved_docs, retrieved_scores)
        ]
        
        results = {}
        for metric in self.metrics:
            metric_name = metric.__class__.__name__.lower()
            if metric_name == "hitrate": metric_name = "hit_rate"
            if metric_name == "exactmatch": metric_name = "exact_match"
            if metric_name == "averagescore": metric_name = "average_score"
            if metric_name == "firstchunkscore": metric_name = "first_chunk_score"
            
            score = metric.calculate(expected_answer, retrieved_chunks, top_k=top_k)
            results[metric_name] = score
        return results

    async def evaluate_single(self, question: str, expected_answer: Union[str, List[str]], top_k: int = 3) -> Dict[str, Any]:
        """
        Run and evaluate a single retrieval.
        """
        output = await retrieve_context(question, top_k=top_k)
        metrics = self.calculate_metrics(expected_answer, output.docs, output.scores, top_k=top_k)
        return {
            "output": output,
            "metrics": metrics
        }
        
    async def evaluate_batch(
        self,
        ground_truth_file: str = "datasets/ground_truth_dataset.json",
        top_k: int = 3,
        run_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run batch evaluation for retrieval.
        """
        if run_name is None:
            # Shorten name
            run_name = f"retrieval-eval-{datetime.now().strftime('%Y%m%d-%H%M')}"

        items = load_ground_truth_dataset(ground_truth_file)
        langfuse_client = get_langfuse_client()
        
        if langfuse_client:
            sync_dataset_to_langfuse(langfuse_client, items)
            
        results = []
        scores_aggregate = {
            "hit_rate": [], 
            "mrr": [], 
            "exact_match": [],
            "average_score": [],
            "first_chunk_score": []
        }
        
        logger.info("Starting retrieval evaluation", extra={"run_name": run_name, "count": len(items)})
        
        for idx, item in enumerate(items):
            eval_res = await self.evaluate_single(item.question, item.expected_chunks, top_k=top_k)
            metrics = eval_res["metrics"]
            output = eval_res["output"]
            
            # Aggregate keys
            for k, v in metrics.items():
                if k in scores_aggregate:
                    scores_aggregate[k].append(v)
            
            results.append({
                "question": item.question,
                "metrics": metrics
            })
            
            # Log to Langfuse
            if langfuse_client:
                trace_id = f"eval-{run_name}-{idx}"
                trace = langfuse_client.trace(
                    id=trace_id,
                    name="retrieval_evaluation",
                    input={"question": item.question},
                    output={"docs": output.docs},
                    metadata={"run_name": run_name}
                )
                
                for name, value in metrics.items():
                    trace.score(
                        name=name,
                        value=value,
                        comment=f"Metric: {name}"
                    )
        
        aggregated = {
            k: sum(v)/len(v) if v else 0.0 for k, v in scores_aggregate.items() 
        }
        
        logger.info("Retrieval evaluation finished", extra={"run_name": run_name, "results": aggregated})
        return {
            "run_name": run_name,
            "metrics": aggregated,
            "details": results
        }

evaluator = RetrievalEvaluator()
