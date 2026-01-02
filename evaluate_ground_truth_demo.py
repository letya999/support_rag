#!/usr/bin/env python3
"""
Ground Truth Retrieval Evaluation - DEMO VERSION
This script demonstrates evaluation metrics (Hit Rate, MRR, Exact Match)
without requiring database connection or embeddings.
Uses mock retrieval results for demonstration.
"""

import json
import os
from typing import List, Dict, Any
from datetime import datetime

def load_ground_truth_dataset(file_path: str) -> List[Dict[str, str]]:
    """Load ground truth dataset"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_qa_data(file_path: str) -> List[Dict[str, str]]:
    """Load original QA data to use as mock chunks"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def check_answer_in_chunk(expected_answer: str, chunk: str) -> bool:
    """
    Check if expected answer is contained in the chunk.
    This handles the case where chunk contains both question and answer.
    """
    chunk_lower = chunk.lower()
    answer_lower = expected_answer.lower()
    return answer_lower in chunk_lower

def generate_mock_retrieved_chunks(test_question: str, qa_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Generate mock retrieved chunks for demo purposes.
    In real scenario, these would come from vector search.

    This simulates retrieval by:
    1. Finding the best matching Q&A pair (by simple string matching)
    2. Creating chunks from the Q&A data
    3. Adding some fuzzy ranking (not perfect match)
    """
    chunks = []

    # Create chunks from all Q&A pairs
    # In real scenario, these would be the actual database documents
    for qa_item in qa_data:
        original_question = qa_item["question"]
        answer = qa_item["answer"]
        chunk_content = f"Question: {original_question}\nAnswer: {answer}"

        # Simple similarity score based on word overlap
        test_words = set(test_question.lower().split())
        original_words = set(original_question.lower().split())
        overlap = len(test_words & original_words)
        # Add small random variance to simulate real ranking
        score = overlap / max(len(test_words), len(original_words)) if test_words else 0

        chunks.append({
            "content": chunk_content,
            "score": score + (0.01 if "how" in test_question.lower() else 0)  # Small tie-breaker
        })

    # Sort by score descending
    chunks.sort(key=lambda x: x["score"], reverse=True)
    return chunks

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

def run_demo_evaluation(top_k: int = 3):
    """
    Run ground truth evaluation with mock data.
    """
    print(f"🚀 Ground Truth Retrieval Evaluation - DEMO MODE (top-k={top_k})...\n")

    # Load datasets
    try:
        ground_truth_data = load_ground_truth_dataset("ground_truth_dataset.json")
        qa_data = load_qa_data("qa_data.json")
        print(f"📦 Loaded {len(ground_truth_data)} test items")
        print(f"📦 Loaded {len(qa_data)} original Q&A pairs\n")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    run_name = f"ground-truth-demo-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"📊 Running evaluation '{run_name}'...\n")

    # Collect all metrics
    all_metrics = []
    hit_rates = []
    mrrs = []
    exact_matches = []

    for idx, item in enumerate(ground_truth_data, start=1):
        question = item["question"]
        expected_answer = item["expected_chunk_answer"]

        print(f"[{idx}/{len(ground_truth_data)}] Evaluating: {question[:60]}...")

        try:
            # Generate mock retrieved chunks
            retrieved_chunks = generate_mock_retrieved_chunks(question, qa_data)

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
    print(f"📊 EVALUATION RESULTS (DEMO MODE)")
    print(f"{'='*60}")
    print(f"Total queries evaluated: {len(all_metrics)}")
    print(f"\n🎯 Hit Rate (Recall@{top_k}): {avg_hit_rate:.4f} ({sum(hit_rates)}/{len(hit_rates)})")
    print(f"  → Percentage of queries where correct answer found in top-{top_k}")
    print(f"\n📈 MRR (Mean Reciprocal Rank): {avg_mrr:.4f}")
    print(f"  → Average reciprocal position of correct answer")
    print(f"\n✅ Exact Match (top-1): {avg_exact_match:.4f} ({sum(exact_matches)}/{len(exact_matches)})")
    print(f"  → Percentage of queries where correct answer is ranked #1")
    print(f"{'='*60}\n")

    # Save results to file
    results = {
        "run_name": run_name,
        "mode": "DEMO (Mock Retrieval)",
        "timestamp": datetime.now().isoformat(),
        "top_k": top_k,
        "total_queries": len(all_metrics),
        "aggregate_metrics": {
            "hit_rate": {
                "value": avg_hit_rate,
                "description": "Recall@K - percentage of queries where correct answer found in top-K"
            },
            "mrr": {
                "value": avg_mrr,
                "description": "Mean Reciprocal Rank - average reciprocal position of correct answer"
            },
            "exact_match": {
                "value": avg_exact_match,
                "description": "Percentage of queries where correct answer is ranked #1"
            },
        },
        "metrics_explanation": {
            "hit_rate": "1 point if expected_chunk_answer found in top-K chunks, 0 otherwise. Average across all queries.",
            "mrr": "1/position of correct chunk. Position 1→1.0, Position 2→0.5, Position 3→0.33, Not found→0. Average across all queries.",
            "exact_match": "1 point if top-1 chunk contains expected_chunk_answer, 0 otherwise. Average across all queries."
        },
        "detailed_results": [
            {k: v for k, v in m.items() if k != "top_1_chunk"}  # Exclude long chunk content
            for m in all_metrics
        ]
    }

    output_file = f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"📁 Detailed results saved to {output_file}")
    print(f"\n✅ Demo evaluation complete!\n")
    print(f"📝 Note: This is a DEMO with mock retrieval results.")
    print(f"🔗 To run real evaluation with actual vector search:")
    print(f"   1. Set OPENAI_API_KEY environment variable")
    print(f"   2. Run: python ingest.py  # Load data into PostgreSQL")
    print(f"   3. Run: python evaluate_ground_truth.py  # Real evaluation")

if __name__ == "__main__":
    run_demo_evaluation(top_k=3)
