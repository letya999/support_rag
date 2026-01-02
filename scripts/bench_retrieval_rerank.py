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
from app.nodes.reranking.ranker import get_reranker
from app.nodes.reranking.evaluator import RerankEvaluator
from app.nodes.retrieval.evaluator import evaluator as base_evaluator

langfuse = get_langfuse_client()

def load_ground_truth(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Dataset not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def run_rerank_bench(args):
    input_path = args.dataset
    if os.path.exists(input_path):
        file_path = input_path
    else:
        if not input_path.endswith(".json"):
            input_path += ".json"
        file_path = os.path.join("datasets", input_path)
    
    dataset_name = os.path.splitext(os.path.basename(file_path))[0]
    top_k_retrieval = args.top_k_retrieval
    top_k_rerank = args.top_k_rerank

    print(f"🚀 Starting Expansion + Retrieval + Reranking Benchmark: {dataset_name}")
    print(f"   (Retrieved: {top_k_retrieval}, Reranked: {top_k_rerank})")
    
    try:
        gt_data = load_ground_truth(file_path)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    if not langfuse:
        print("❌ Langfuse client not initialized.")
        return
        
    dataset = langfuse.get_dataset(dataset_name)
    run_name = f"rerank-bench-{dataset_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    all_retrieval_metrics = []
    all_rerank_metrics = []
    expander = QueryExpander()
    ranker = get_reranker()
    
    print(f"\n📊 Evaluating {len(dataset.items)} items...\n")

    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        
        print(f"[{i}/{len(dataset.items)}] {question[:40]}...", end=" ", flush=True)
        
        with item.run(run_name=run_name) as trace:
            try:
                # 1. Expansion
                expanded_queries = await expander.expand(question)
                
                # 2. Base Retrieval (Top-K before rerank)
                retrieval_output = await retrieve_context(expanded_queries, top_k=top_k_retrieval)
                base_metrics = base_evaluator.calculate_metrics(
                    expected_chunks, 
                    retrieval_output.docs, 
                    retrieval_output.scores, 
                    top_k=top_k_retrieval
                )
                
                # Log Base Metrics
                for m_name, m_val in base_metrics.items():
                    trace.score(name=f"base_{m_name}", value=float(m_val))
                all_retrieval_metrics.append(base_metrics)

                # 3. Reranking
                ranked_results = ranker.rank(question, retrieval_output.docs)
                reranked_docs = [doc for score, doc in ranked_results][:top_k_rerank]
                reranked_scores = [score for score, doc in ranked_results][:top_k_rerank]
                
                # 4. Rerank Metrics
                rerank_metrics = base_evaluator.calculate_metrics(
                    expected_chunks, 
                    reranked_docs, 
                    reranked_scores, 
                    top_k=top_k_rerank
                )
                
                trace.update(
                    input={"question": question, "expanded_queries": expanded_queries},
                    output={
                        "base_docs_count": len(retrieval_output.docs),
                        "reranked_docs": reranked_docs, 
                        "base_metrics": base_metrics,
                        "rerank_metrics": rerank_metrics
                    }
                )
                
                for m_name, m_val in rerank_metrics.items():
                    trace.score(name=f"rerank_{m_name}", value=float(m_val))
                
                all_rerank_metrics.append(rerank_metrics)
                
                # Terminal output with "increasing" metrics
                print(f"| Base Hit@{top_k_retrieval}: {base_metrics['hit_rate']:.2f} MRR: {base_metrics['mrr']:.2f} "
                      f"-> Rerank Hit@{top_k_rerank}: {rerank_metrics['hit_rate']:.2f} MRR: {rerank_metrics['mrr']:.2f}")

            except Exception as e:
                print(f"⚠️ Error: {e}")
                continue

    # Summary
    if all_rerank_metrics:
        def avg(metrics_list, key):
            return sum(m[key] for m in metrics_list) / len(metrics_list)

        print(f"\n{'='*60}")
        print(f"🏁 BENCHMARK SUMMARY: {dataset_name}")
        print(f"{'-'*60}")
        print(f"Metrics:             | Base (k={top_k_retrieval}) | Rerank (k={top_k_rerank})")
        print(f"Avg Hit Rate:        | {avg(all_retrieval_metrics, 'hit_rate'):.4f}      | {avg(all_rerank_metrics, 'hit_rate'):.4f}")
        print(f"Avg MRR:             | {avg(all_retrieval_metrics, 'mrr'):.4f}      | {avg(all_rerank_metrics, 'mrr'):.4f}")
        print(f"Avg Vector Score:    | {avg(all_retrieval_metrics, 'average_score'):.4f}      | {avg(all_rerank_metrics, 'average_score'):.4f}")
        print(f"{'='*60}")

    langfuse.flush()
    print(f"\n✅ Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run reranking benchmark.")
    parser.add_argument("dataset", help="Dataset name")
    parser.add_argument("--top_k_retrieval", type=int, default=10, help="Docs to retrieve before reranking")
    parser.add_argument("--top_k_rerank", type=int, default=5, help="Docs to keep after reranking")
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_rerank_bench(args))
