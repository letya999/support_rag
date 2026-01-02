"""LangGraph Integration for Ground Truth Evaluation

Provides a node for evaluating retrieval quality within LangGraph workflows.
Can be added after retrieval or as a separate evaluation step.
"""

from typing import Any, Dict, Optional
from langfuse import Langfuse

from app.ground_truth.evaluator import evaluate_ground_truth


async def evaluation_node(
    state: Dict[str, Any],
    langfuse_client: Optional[Langfuse] = None,
    ground_truth_file: str = "ground_truth_dataset.json",
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    LangGraph node for Ground Truth evaluation.

    This node evaluates the retrieval performance using ground truth dataset
    and logs metrics to Langfuse for monitoring.

    Usage in LangGraph:
        workflow.add_node("ground_truth_eval", evaluation_node)
        workflow.add_edge("retrieval", "ground_truth_eval")

    Args:
        state: LangGraph state containing the conversation
        langfuse_client: Langfuse client for logging
        ground_truth_file: Path to ground truth dataset
        top_k: Number of top results to consider

    Returns:
        Updated state with evaluation results
    """
    results = await evaluate_ground_truth(
        langfuse_client=langfuse_client,
        ground_truth_file=ground_truth_file,
        top_k=top_k,
        run_name=f"rag-eval-{state.get('run_id', 'default')}"
    )

    if results:
        state["ground_truth_evaluation"] = {
            "status": "success",
            "metrics": results["aggregate_metrics"],
            "total_queries": results["total_queries"],
            "run_name": results["run_name"],
        }
    else:
        state["ground_truth_evaluation"] = {
            "status": "failed",
            "error": "Evaluation failed",
        }

    return state


def log_metrics_to_trace(
    langfuse_client: Optional[Langfuse],
    trace_id: str,
    metrics: Dict[str, float],
    found_at_position: Optional[int] = None,
) -> None:
    """
    Log Ground Truth metrics to an existing Langfuse trace.

    Can be called from any node to log retrieval evaluation metrics
    for a specific trace.

    Args:
        langfuse_client: Langfuse client
        trace_id: Trace ID to log metrics to
        metrics: Dictionary with hit_rate, mrr, exact_match
        found_at_position: Position where correct answer was found
    """
    if langfuse_client is None:
        return

    try:
        langfuse_client.create_score(
            trace_id=trace_id,
            name="hit_rate",
            value=float(metrics.get("hit_rate", 0)),
        )
        langfuse_client.create_score(
            trace_id=trace_id,
            name="mrr",
            value=float(metrics.get("mrr", 0)),
        )
        langfuse_client.create_score(
            trace_id=trace_id,
            name="exact_match",
            value=float(metrics.get("exact_match", 0)),
        )

        if found_at_position:
            langfuse_client.create_score(
                trace_id=trace_id,
                name="found_at_position",
                value=float(found_at_position),
            )

        langfuse_client.flush()
    except Exception as e:
        print(f"⚠️ Failed to log metrics: {e}")
