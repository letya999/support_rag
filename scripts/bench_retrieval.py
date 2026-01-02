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
from app.integrations.embeddings import get_embedding
from app.storage.vector_store import search_documents
from app.nodes.retrieval.evaluator import evaluator

langfuse = get_langfuse_client()

def load_ground_truth(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Dataset not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_to_langfuse(data: List[Dict], dataset_name: str):
    """Syncs dataset to Langfuse if not already present."""
    if not langfuse:
        return
    try:
        langfuse.get_dataset(dataset_name)
        print(f"✅ Dataset '{dataset_name}' already exists in Langfuse.")
    except Exception:
        print(f"📦 Creating dataset '{dataset_name}' in Langfuse...")
        langfuse.create_dataset(name=dataset_name)
        for item in data:
            langfuse.create_dataset_item(
                dataset_name=dataset_name,
                input={"question": item["question"]},
                expected_output={
                    "expected_chunks": item.get("expected_chunks", []),
                    "expected_answer": item.get("expected_answer"),
                    "intent": item.get("expected_intent")
                }
            )
        print(f"✅ Uploaded {len(data)} items.")

async def run_retrieval_bench(args):
    # Determine the file path
    input_path = args.dataset
    if os.path.exists(input_path):
        file_path = input_path
    else:
        if not input_path.endswith(".json"):
            input_path += ".json"
        file_path = os.path.join("datasets", input_path)
    
    # Dataset name in Langfuse depends on the filename
    dataset_name = os.path.splitext(os.path.basename(file_path))[0]

    top_k = args.top_k

    print(f"🚀 Starting Retrieval Benchmark: {dataset_name} (top_k={top_k})")
    
    # 1. Load and Sync
    try:
        gt_data = load_ground_truth(file_path)
        sync_to_langfuse(gt_data, dataset_name)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # 2. Get Dataset Items
    if not langfuse:
        print("❌ Langfuse client not initialized.")
        return
        
    dataset = langfuse.get_dataset(dataset_name)
    run_name = f"retrieval-{dataset_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    all_metrics = []
    
    print(f"\n📊 Evaluating {len(dataset.items)} items...\n")

    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        
        print(f"[{i}/{len(dataset.items)}] {question[:50]}...", end=" ", flush=True)
        
        # Link this run to the dataset item
        with item.run(run_name=run_name) as trace:
            try:
                # 3. Retrieval & Metrics
                eval_res = await evaluator.evaluate_single(question, expected_chunks, top_k=top_k)
                metrics = eval_res["metrics"]
                retrieved_contents = eval_res["output"].docs
                
                # 5. Log results to Trace
                trace.update(
                    input={"question": question},
                    output={"retrieved_docs": retrieved_contents, "metrics": metrics}
                )
                
                # Create scores in Langfuse
                for m_name, m_val in metrics.items():
                    trace.score(
                        name=f"retrieval_{m_name}",
                        value=float(m_val)
                    )
                
                all_metrics.append(metrics)
                print(f"Hit: {metrics['hit_rate']} MRR: {metrics['mrr']:.2f} AvgScore: {metrics['average_score']:.3f} TopScore: {metrics['first_chunk_score']:.3f}")

            except Exception as e:
                print(f"⚠️ Error processing item: {e}")
                continue

    # 6. Aggregate results
    if all_metrics:
        avg_hit = sum(m["hit_rate"] for m in all_metrics) / len(all_metrics)
        avg_mrr = sum(m["mrr"] for m in all_metrics) / len(all_metrics)
        avg_em = sum(m["exact_match"] for m in all_metrics) / len(all_metrics)
        avg_score = sum(m["average_score"] for m in all_metrics) / len(all_metrics)
        avg_first = sum(m["first_chunk_score"] for m in all_metrics) / len(all_metrics)
        
        print(f"\n{'='*40}")
        print(f"🏁 BENCHMARK SUMMARY")
        print(f"{'='*40}")
        print(f"Dataset:            {dataset_name}")
        print(f"Avg Hit Rate@{top_k}: {avg_hit:.4f}")
        print(f"Avg MRR@{top_k}:      {avg_mrr:.4f}")
        print(f"Avg Exact Match:   {avg_em:.4f}")
        print(f"Avg Vector Score:  {avg_score:.4f}")
        print(f"Avg Top Chunk Sc.: {avg_first:.4f}")
        print(f"{'='*40}")
        
        # Aggregates are calculated automatically by Langfuse on the dataset run level.

    langfuse.flush()
    print(f"\n✅ Done! Check Langfuse dataset '{dataset_name}' → run '{run_name}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run retrieval benchmark on a dataset.")
    parser.add_argument("dataset", help="Name of the dataset file in 'datasets/' (e.g., ground_truth_dataset)")
    parser.add_argument("--top_k", type=int, default=3, help="Number of documents to retrieve (default: 3)")
    
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_retrieval_bench(args))
