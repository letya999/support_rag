import os
import sys
import asyncio
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.observability.langfuse_client import get_langfuse_client
from app.nodes.query_expansion.expander import QueryExpander
from app.nodes.retrieval.search import retrieve_context
from app.nodes.retrieval.evaluator import evaluator

langfuse = get_langfuse_client()

def load_ground_truth(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Dataset not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def run_expansion_bench(args):
    # Determine the file path
    input_path = args.dataset
    if os.path.exists(input_path):
        file_path = input_path
    else:
        if not input_path.endswith(".json"):
            input_path += ".json"
        file_path = os.path.join("datasets", input_path)
    
    dataset_name = os.path.splitext(os.path.basename(file_path))[0]
    top_k = args.top_k

    print(f"🚀 Starting Retrieval + Expansion Benchmark: {dataset_name} (top_k={top_k})")
    
    # Load data
    try:
        gt_data = load_ground_truth(file_path)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    if not langfuse:
        print("❌ Langfuse client not initialized.")
        return
        
    dataset = langfuse.get_dataset(dataset_name)
    run_name = f"expansion-retrieval-{dataset_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    all_metrics = []
    expander = QueryExpander()
    
    print(f"\n📊 Evaluating {len(dataset.items)} items...\n")

    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        
        print(f"[{i}/{len(dataset.items)}] {question[:50]}...", end=" ", flush=True)
        
        with item.run(run_name=run_name) as trace:
            try:
                # 1. Query Expansion
                expanded_queries = await expander.expand(question)
                trace.update(metadata={"expanded_queries": expanded_queries})
                
                # 2. Retrieval with multiple queries
                output = await retrieve_context(expanded_queries, top_k=top_k)
                
                # 3. Metrics
                metrics = evaluator.calculate_metrics(expected_chunks, output.docs, output.scores, top_k=top_k)
                
                # Log results to Trace
                trace.update(
                    input={"question": question, "expanded_queries": expanded_queries},
                    output={"retrieved_docs": output.docs, "metrics": metrics}
                )
                
                for m_name, m_val in metrics.items():
                    trace.score(name=m_name, value=float(m_val))
                
                all_metrics.append(metrics)
                print(f"Hit: {metrics['hit_rate']} MRR: {metrics['mrr']:.2f}")

            except Exception as e:
                print(f"⚠️ Error processing item: {e}")
                continue

    # Summary
    if all_metrics:
        avg_hit = sum(m["hit_rate"] for m in all_metrics) / len(all_metrics)
        avg_mrr = sum(m["mrr"] for m in all_metrics) / len(all_metrics)
        
        print(f"\n{'='*40}")
        print(f"🏁 EXPANSION BENCHMARK SUMMARY")
        print(f"{'='*40}")
        print(f"Dataset:            {dataset_name}")
        print(f"Avg Hit Rate@{top_k}: {avg_hit:.4f}")
        print(f"Avg MRR@{top_k}:      {avg_mrr:.4f}")
        print(f"{'='*40}")

    langfuse.flush()
    print(f"\n✅ Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run expansion + retrieval benchmark.")
    parser.add_argument("dataset", help="Dataset name")
    parser.add_argument("--top_k", type=int, default=3, help="top_k")
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_expansion_bench(args))
