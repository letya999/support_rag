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

from langfuse import Langfuse
from app.embeddings import get_embedding
from app.search import search_documents
from app.ground_truth.metrics import calculate_all_metrics, find_answer_position

langfuse = Langfuse()

def load_ground_truth(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Dataset not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_to_langfuse(data: List[Dict], dataset_name: str):
    """Syncs dataset to Langfuse if not already present."""
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
                expected_output={"answer": item["expected_chunk_answer"]}
            )
        print(f"✅ Uploaded {len(data)} items.")

async def run_retrieval_bench(args):
    dataset_file = args.dataset
    if not dataset_file.endswith(".json"):
        dataset_file += ".json"
    
    # Path inside datasets/
    file_path = os.path.join("datasets", dataset_file)
    
    # Dataset name in Langfuse (e.g., 'ground_truth_dataset' from 'ground_truth_dataset.json')
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
    dataset = langfuse.get_dataset(dataset_name)
    run_name = f"retrieval-{dataset_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    all_metrics = []
    
    print(f"\n📊 Evaluating {len(dataset.items)} items...\n")

    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_answer = item.expected_output["answer"]
        
        print(f"[{i}/{len(dataset.items)}] {question[:50]}...", end=" ", flush=True)
        
        # Link this run to the dataset item
        with item.run(run_name=run_name) as trace:
            try:
                # 3. Retrieval
                emb = await get_embedding(question)
                results = await search_documents(emb, top_k=top_k)
                retrieved_contents = [r["content"] for r in results]
                
                # 4. Calculate Metrics
                metrics = calculate_all_metrics(expected_answer, [{"content": c} for c in retrieved_contents], top_k=top_k)
                pos = find_answer_position(expected_answer, [{"content": c} for c in retrieved_contents])
                
                # 5. Log results to Trace
                trace.update(
                    input={"question": question},
                    output={"retrieved_docs": retrieved_contents, "metrics": metrics, "pos": pos}
                )
                
                # Create scores in Langfuse
                for m_name, m_val in metrics.items():
                    langfuse.create_score(
                        trace_id=trace.trace_id,
                        name=f"retrieval_{m_name}",
                        value=float(m_val)
                    )
                
                if pos:
                    langfuse.create_score(trace_id=trace.trace_id, name="retrieval_position", value=float(pos))

                all_metrics.append(metrics)
                print(f"Hit: {metrics['hit_rate']} MRR: {metrics['mrr']:.2f}")

            except Exception as e:
                print(f"⚠️ Error processing item: {e}")
                continue

    # 6. Aggregate results
    if all_metrics:
        avg_hit = sum(m["hit_rate"] for m in all_metrics) / len(all_metrics)
        avg_mrr = sum(m["mrr"] for m in all_metrics) / len(all_metrics)
        avg_em = sum(m["exact_match"] for m in all_metrics) / len(all_metrics)
        
        print(f"\n{'='*40}")
        print(f"🏁 BENCHMARK SUMMARY")
        print(f"{'='*40}")
        print(f"Dataset:            {dataset_name}")
        print(f"Avg Hit Rate@{top_k}: {avg_hit:.4f}")
        print(f"Avg MRR@{top_k}:      {avg_mrr:.4f}")
        print(f"Avg Exact Match:   {avg_em:.4f}")
        print(f"{'='*40}")
        
        # Log aggregates
        langfuse.create_score(name=f"avg_hit_rate_{dataset_name}", value=avg_hit, comment=f"Run: {run_name}")
        langfuse.create_score(name=f"avg_mrr_{dataset_name}", value=avg_mrr, comment=f"Run: {run_name}")

    langfuse.flush()
    print(f"\n✅ Done! Check Langfuse dataset '{dataset_name}' → run '{run_name}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run retrieval benchmark on a dataset.")
    parser.add_argument("dataset", help="Name of the dataset file in 'datasets/' (e.g., ground_truth_dataset)")
    parser.add_argument("--top_k", type=int, default=3, help="Number of documents to retrieve (default: 3)")
    
    args = parser.parse_args()
    asyncio.run(run_retrieval_bench(args))
