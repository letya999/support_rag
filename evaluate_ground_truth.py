#!/usr/bin/env python3
"""
Evaluate retrieval performance using Ground Truth dataset.
Metrics: Hit Rate (Recall@K), MRR (Mean Reciprocal Rank), Exact Match
No LLM calls - pure retrieval evaluation.
"""

import json
import os
import asyncio
import nest_asyncio
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from app.embeddings import get_embedding
from app.search import search_documents

nest_asyncio.apply()

# Langfuse is optional
LANGFUSE_AVAILABLE = False
try:
    from langfuse import Langfuse
    langfuse = Langfuse()
    LANGFUSE_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Langfuse not available: {e}")
    langfuse = None

DATASET_NAME = "ground-truth-retrieval-eval"

def load_ground_truth_dataset(file_path: str) -> List[Dict[str, str]]:
    """Load ground truth dataset"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_dataset_to_langfuse(test_data: List[Dict[str, str]]):
    """Sync ground truth dataset to Langfuse if available"""
    if not LANGFUSE_AVAILABLE or langfuse is None:
        print(f"⚠️ Langfuse not available, skipping dataset sync")
        return

    try:
        langfuse.get_dataset(DATASET_NAME)
        print(f"✅ Dataset '{DATASET_NAME}' already exists in Langfuse.")
    except Exception:
        print(f"📦 Creating dataset '{DATASET_NAME}' in Langfuse...")
        try:
            langfuse.create_dataset(name=DATASET_NAME)
            for item in test_data:
                langfuse.create_dataset_item(
                    dataset_name=DATASET_NAME,
                    input={"question": item["question"]},
                    expected_output={"answer": item["expected_chunk_answer"]}
                )
            print(f"✅ Uploaded {len(test_data)} items to Langfuse dataset.")
        except Exception as e:
            print(f"⚠️ Failed to sync dataset to Langfuse: {e}")

def extract_answer_from_chunk(chunk: str) -> str:
    """
    Extract answer part from chunk.
    Chunk format: "Question: ...\nAnswer: ..."
    """
    if "Answer:" in chunk:
        return chunk.split("Answer:")[-1].strip()
    return chunk

def check_answer_in_chunk(expected_answer: str, chunk: str) -> bool:
    """
    Check if expected answer is contained in the chunk.
    This handles the case where chunk contains both question and answer.
    """
    chunk_lower = chunk.lower()
    answer_lower = expected_answer.lower()
    # Check if the answer is in the chunk (with some tolerance for exact matching)
    return answer_lower in chunk_lower

def calculate_metrics(
    question: str,
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 3
) -> Dict[str, Any]:
    """
    Calculate metrics for a single query.

    Returns:
    {
        "hit_rate": 1 if found in top-k else 0,
        "mrr": reciprocal rank (1.0, 0.5, 0.33, 0.0),
        "exact_match": 1 if top-1 matches else 0,
        "found_at_position": position (1-based) or None,
        "top_1_chunk": retrieved_chunks[0]["content"] if exists,
    }
    """
    metrics = {
        "question": question,
        "hit_rate": 0,
        "mrr": 0.0,
        "exact_match": 0,
        "found_at_position": None,
        "top_1_chunk": retrieved_chunks[0]["content"] if retrieved_chunks else None,
    }

    # Check each retrieved chunk
    for position, chunk_data in enumerate(retrieved_chunks[:top_k], start=1):
        chunk = chunk_data["content"]

        if check_answer_in_chunk(expected_answer, chunk):
            metrics["hit_rate"] = 1
            metrics["found_at_position"] = position
            # Calculate MRR
            metrics["mrr"] = 1.0 / position
            # Exact match only if it's the first result
            if position == 1:
                metrics["exact_match"] = 1
            break

    return metrics

async def run_evaluation(top_k: int = 3):
    """
    Run ground truth evaluation.
    """
    print(f"🚀 Starting Ground Truth Retrieval Evaluation (top-k={top_k})...\n")

    # Load ground truth dataset
    try:
        test_data = load_ground_truth_dataset("ground_truth_dataset.json")
        print(f"📦 Loaded {len(test_data)} test items\n")
        sync_dataset_to_langfuse(test_data)
    except Exception as e:
        print(f"❌ Error loading/syncing data: {e}")
        return

    run_name = f"ground-truth-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"📊 Running evaluation '{run_name}' on {len(test_data)} items...\n")

    # Collect all metrics
    all_metrics = []
    hit_rates = []
    mrrs = []
    exact_matches = []

    for idx, item in enumerate(test_data, start=1):
        question = item["question"]
        expected_answer = item["expected_chunk_answer"]

        print(f"[{idx}/{len(test_data)}] Evaluating: {question[:60]}...")

        try:
            # Get embedding and retrieve
            embedding = await get_embedding(question)
            retrieved_chunks = await search_documents(embedding, top_k=top_k)

            # Calculate metrics
            metrics = calculate_metrics(
                question=question,
                expected_answer=expected_answer,
                retrieved_chunks=retrieved_chunks,
                top_k=top_k
            )

            # Collect metrics
            all_metrics.append(metrics)
            hit_rates.append(metrics["hit_rate"])
            mrrs.append(metrics["mrr"])
            exact_matches.append(metrics["exact_match"])

            # Log individual scores to Langfuse if available
            if LANGFUSE_AVAILABLE and langfuse:
                try:
                    trace_id = f"trace-{idx}"
                    langfuse.create_score(
                        trace_id=trace_id,
                        name="hit_rate",
                        value=float(metrics["hit_rate"]),
                    )
                    langfuse.create_score(
                        trace_id=trace_id,
                        name="mrr",
                        value=metrics["mrr"],
                    )
                    langfuse.create_score(
                        trace_id=trace_id,
                        name="exact_match",
                        value=float(metrics["exact_match"]),
                    )
                except Exception:
                    pass  # Langfuse logging is optional

            # Print individual result
            position_str = f"@pos {metrics['found_at_position']}" if metrics["found_at_position"] else "not found"
            print(f"  ✓ Hit: {metrics['hit_rate']}, MRR: {metrics['mrr']:.2f}, Exact: {metrics['exact_match']} ({position_str})")

        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            continue

    if not all_metrics:
        print("❌ No data processed successfully.")
        return

    # Calculate aggregate metrics
    avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0
    avg_mrr = sum(mrrs) / len(mrrs) if mrrs else 0
    avg_exact_match = sum(exact_matches) / len(exact_matches) if exact_matches else 0

    print(f"\n{'='*60}")
    print(f"📊 EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"Total queries evaluated: {len(all_metrics)}")
    print(f"\n🎯 Hit Rate (Recall@{top_k}): {avg_hit_rate:.4f} ({sum(hit_rates)}/{len(hit_rates)})")
    print(f"📈 MRR (Mean Reciprocal Rank): {avg_mrr:.4f}")
    print(f"✅ Exact Match (top-1): {avg_exact_match:.4f} ({sum(exact_matches)}/{len(exact_matches)})")
    print(f"{'='*60}\n")

    # Save results to file
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
    print(f"📁 Detailed results saved to {output_file}")

    # Create aggregate scores in Langfuse if available
    if LANGFUSE_AVAILABLE and langfuse:
        try:
            print(f"\n📈 Recording aggregate scores in Langfuse...")
            langfuse.create_score(
                name="hit_rate_aggregate",
                value=avg_hit_rate,
                comment=f"Hit Rate @{top_k} for run {run_name}",
            )
            langfuse.create_score(
                name="mrr_aggregate",
                value=avg_mrr,
                comment=f"MRR for run {run_name}",
            )
            langfuse.create_score(
                name="exact_match_aggregate",
                value=avg_exact_match,
                comment=f"Exact Match for run {run_name}",
            )
            langfuse.flush()
            print(f"✅ Scores recorded in Langfuse")
        except Exception as e:
            print(f"⚠️ Failed to record scores in Langfuse: {e}")

    print(f"\n✅ Evaluation complete!")

async def main():
    """Main entry point"""
    await run_evaluation(top_k=3)

if __name__ == "__main__":
    asyncio.run(main())
