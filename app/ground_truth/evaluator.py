"""Ground Truth Matching Evaluator"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from langfuse import Langfuse

from app.search import search_documents
from app.embeddings import get_embedding
from app.ground_truth.metrics import (
    calculate_hit_rate,
    calculate_mrr,
    calculate_exact_match,
    calculate_all_metrics,
    find_answer_position,
)
from app.ground_truth.dataset_sync import load_ground_truth_dataset, sync_dataset_to_langfuse, DATASET_NAME


async def evaluate_ground_truth(
    langfuse_client: Optional[Langfuse] = None,
    ground_truth_file: str = "ground_truth_dataset.json",
    top_k: int = 3,
    run_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate retrieval performance using ground truth dataset.

    This function:
    1. Loads ground truth dataset
    2. For each question, retrieves chunks from search_documents()
    3. Calculates metrics (Hit Rate, MRR, Exact Match)
    4. Logs results to Langfuse (if available)
    5. Returns aggregate metrics

    Args:
        langfuse_client: Langfuse client (optional)
        ground_truth_file: Path to ground truth dataset JSON
        top_k: Number of top results to consider
        run_name: Custom run name (auto-generated if None)

    Returns:
        {
            "run_name": str,
            "timestamp": str,
            "top_k": int,
            "total_queries": int,
            "aggregate_metrics": {
                "hit_rate": float,
                "mrr": float,
                "exact_match": float,
            },
            "detailed_results": List[Dict]
        }
    """
    if run_name is None:
        run_name = f"ground-truth-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"🚀 Starting Ground Truth Evaluation: {run_name}")
    print(f"📊 Dataset: {ground_truth_file}, top_k={top_k}\n")

    # Load and sync dataset
    try:
        ground_truth_data = load_ground_truth_dataset(ground_truth_file)
        print(f"📦 Loaded {len(ground_truth_data)} test items")

        if langfuse_client:
            sync_dataset_to_langfuse(langfuse_client, ground_truth_data)
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        return None

    # Evaluate each item
    all_metrics = []
    hit_rates = []
    mrrs = []
    exact_matches = []

    print(f"\n📊 Evaluating {len(ground_truth_data)} queries...\n")

    for idx, item in enumerate(ground_truth_data, start=1):
        question = item["question"]
        expected_answer = item["expected_chunk_answer"]

        print(f"[{idx}/{len(ground_truth_data)}] {question[:60]}...", end=" ")

        try:
            # Get embedding and retrieve
            embedding = await get_embedding(question)
            retrieved_chunks = await search_documents(embedding, top_k=top_k)

            # Calculate metrics
            metrics = calculate_all_metrics(expected_answer, retrieved_chunks, top_k)

            # Find position of correct answer
            found_at_position = None
            for pos, chunk_data in enumerate(retrieved_chunks[:top_k], start=1):
                if expected_answer.lower() in chunk_data["content"].lower():
                    found_at_position = pos
                    break

            # Prepare result
            result = {
                "question": question,
                "expected_answer": expected_answer,
                "found_at_position": found_at_position,
                **metrics
            }

            all_metrics.append(result)
            hit_rates.append(metrics["hit_rate"])
            mrrs.append(metrics["mrr"])
            exact_matches.append(metrics["exact_match"])

            # Log to Langfuse
            if langfuse_client:
                _log_to_langfuse(
                    langfuse_client,
                    trace_id=f"gt-{run_name}-{idx}",
                    question=question,
                    expected_answer=expected_answer,
                    retrieved_chunks=retrieved_chunks[:top_k],
                    metrics=metrics,
                    found_at_position=found_at_position,
                    run_name=run_name
                )

            # Print result
            pos_str = f"@{found_at_position}" if found_at_position else "❌"
            print(f"Hit:{metrics['hit_rate']} MRR:{metrics['mrr']:.2f} EM:{metrics['exact_match']} {pos_str}")

        except Exception as e:
            print(f"⚠️ Error: {e}")
            continue

    # Calculate aggregates
    if not all_metrics:
        print("❌ No successful evaluations")
        return None

    avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0
    avg_mrr = sum(mrrs) / len(mrrs) if mrrs else 0
    avg_exact_match = sum(exact_matches) / len(exact_matches) if exact_matches else 0

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Run: {run_name}")
    print(f"Queries: {len(all_metrics)}/{len(ground_truth_data)}")
    print(f"\n🎯 Hit Rate@{top_k}: {avg_hit_rate:.4f} ({int(sum(hit_rates))}/{len(hit_rates)})")
    print(f"📈 MRR: {avg_mrr:.4f}")
    print(f"✅ Exact Match: {avg_exact_match:.4f} ({int(sum(exact_matches))}/{len(exact_matches)})")
    print(f"{'='*60}\n")

    # Save results
    results = {
        "run_name": run_name,
        "timestamp": datetime.now().isoformat(),
        "top_k": top_k,
        "total_queries": len(all_metrics),
        "aggregate_metrics": {
            "hit_rate": avg_hit_rate,
            "mrr": avg_mrr,
            "exact_match": avg_exact_match,
        },
        "detailed_results": all_metrics,
    }

    output_file = f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Results saved: {output_file}\n")

    # Log aggregate scores
    if langfuse_client:
        _log_aggregate_scores(langfuse_client, run_name, avg_hit_rate, avg_mrr, avg_exact_match, top_k)

    return results


def _log_to_langfuse(
    langfuse_client: Langfuse,
    trace_id: str,
    question: str,
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    metrics: Dict[str, float],
    found_at_position: Optional[int],
    run_name: str
) -> None:
    """
    Log evaluation result and metrics to Langfuse.

    Logs:
    - Trace with input (question) and output (retrieved chunks, metrics)
    - Individual scores for each metric:
      - hit_rate: 0 or 1 (found in top-K)
      - mrr: reciprocal rank (1/position)
      - exact_match: 0 or 1 (top-1 is correct)
    """
    try:
        # Create trace with evaluation details
        trace = langfuse_client.trace(
            id=trace_id,
            name="ground_truth_eval",
            input={"question": question},
            output={
                "retrieved_chunks": [
                    {
                        "content": c["content"][:200],
                        "score": c.get("score", 0)
                    }
                    for c in retrieved_chunks
                ],
                "expected_answer": expected_answer,
                "found_at_position": found_at_position,
            },
            metadata={
                "run_name": run_name,
                "eval_type": "ground_truth_retrieval",
                "top_k": len(retrieved_chunks),
            }
        )

        # Log Hit Rate score
        # Measures if correct answer found in top-K results
        langfuse_client.create_score(
            trace_id=trace_id,
            name="hit_rate",
            value=float(metrics["hit_rate"]),
            comment=f"Found in top-{len(retrieved_chunks)}" if metrics["hit_rate"] else "Not found in results",
        )

        # Log MRR score
        # Measures reciprocal position (1.0 for position 1, 0.5 for position 2, etc.)
        mrr_comment = f"Position: {int(1/metrics['mrr'])}" if metrics["mrr"] > 0 else "Not found"
        langfuse_client.create_score(
            trace_id=trace_id,
            name="mrr",
            value=metrics["mrr"],
            comment=mrr_comment,
        )

        # Log Exact Match score
        # Measures if top-1 result is correct
        langfuse_client.create_score(
            trace_id=trace_id,
            name="exact_match",
            value=float(metrics["exact_match"]),
            comment="Top-1 is correct" if metrics["exact_match"] else "Top-1 is incorrect",
        )

        langfuse_client.flush()

    except Exception as e:
        pass  # Langfuse logging is optional


def _log_aggregate_scores(
    langfuse_client: Langfuse,
    run_name: str,
    hit_rate: float,
    mrr: float,
    exact_match: float,
    top_k: int
) -> None:
    """
    Log aggregate (run-level) evaluation scores to Langfuse.

    These are overall metrics across all test queries, useful for
    tracking performance over time and comparing different runs.
    """
    try:
        # Hit Rate aggregate: % of queries where correct answer found in top-K
        langfuse_client.create_score(
            name="hit_rate_aggregate",
            value=hit_rate,
            comment=f"Hit Rate@{top_k}: {hit_rate*100:.1f}% of queries found correct answer in top-{top_k} (run: {run_name})",
        )

        # MRR aggregate: average reciprocal position
        langfuse_client.create_score(
            name="mrr_aggregate",
            value=mrr,
            comment=f"MRR: average reciprocal rank = {mrr:.4f} (run: {run_name})",
        )

        # Exact Match aggregate: % of queries where top-1 is correct
        langfuse_client.create_score(
            name="exact_match_aggregate",
            value=exact_match,
            comment=f"Exact Match: {exact_match*100:.1f}% of queries have correct answer at top-1 (run: {run_name})",
        )

        langfuse_client.flush()
        print("✅ Aggregate scores logged to Langfuse")
    except Exception as e:
        print(f"⚠️ Failed to log aggregate scores: {e}")
