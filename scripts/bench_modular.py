import os
import sys
import asyncio
import argparse
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.observability.langfuse_client import get_langfuse_client
from app.nodes.retrieval.search import retrieve_context, retrieve_context_expanded
from app.nodes.retrieval.evaluator import evaluator
from app.nodes.classification.classifier import ClassificationService
from app.nodes.easy_classification.fasttext_classifier import FastTextClassificationService
from app.nodes.classification.evaluator import evaluator as cls_evaluator
from app.nodes.easy_classification.evaluator import evaluator as ft_evaluator

langfuse = get_langfuse_client()

async def run_modular_bench(args):
    dataset_name = args.dataset
    if dataset_name.endswith(".json"):
        dataset_name = dataset_name[:-5]
    
    # top_k settings
    top_k_retrieval = args.top_k_retrieval
    top_k_rerank = args.top_k_rerank if args.use_reranker else None
    
    print(f"🚀 Modular Benchmark: {dataset_name}")
    print(f"   Expansion: {'ON' if args.use_expansion else 'OFF'}")
    print(f"   Hybrid:    {'ON' if args.use_hybrid else 'OFF'}")
    print(f"   Classifier (Zero-Shot): {'ON' if args.use_classifier else 'OFF'}")
    print(f"   Classifier (FastText):  {'ON' if args.use_fasttext else 'OFF'}")
    print(f"   Reranker:  {'ON' if args.use_reranker else 'OFF'} (k={top_k_rerank})")

    classifier = ClassificationService() if args.use_classifier else None
    ft_classifier = FastTextClassificationService() if args.use_fasttext else None

    if not langfuse:
        print("❌ Langfuse client not initialized.")
        return
        
    dataset = langfuse.get_dataset(dataset_name)
    run_name = f"mod-bench-{datetime.now().strftime('%m%d-%H%M')}"
    
    all_metrics = []
    cls_results = {"zs": {"true": [], "pred": [], "conf": []}, "ft": {"true": [], "pred": [], "conf": []}}
    
    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        gt_category = item.metadata.get("category") if item.metadata else None
        
        print(f"[{i}/{len(dataset.items)}] {question[:40]}...", end=" ", flush=True)
        
        with item.run(run_name=run_name) as trace:
            try:
                # Classification
                category_filter = None
                
                # Zero-Shot Classifier
                if classifier:
                    cls_res = await classifier.classify(question)
                    cls_results["zs"]["pred"].append(cls_res.category)
                    cls_results["zs"]["conf"].append(cls_res.category_confidence)
                    if gt_category:
                        cls_results["zs"]["true"].append(gt_category)
                    category_filter = cls_res.category if cls_res.category_confidence >= args.confidence_threshold else None

                # FastText Classifier
                if ft_classifier:
                    ft_res = await ft_classifier.classify(question)
                    if ft_res:
                        cls_results["ft"]["pred"].append(ft_res.category)
                        cls_results["ft"]["conf"].append(ft_res.category_confidence)
                        if gt_category:
                            cls_results["ft"]["true"].append(gt_category)
                        # We prioritize FT for filtering if ZS is disabled or if we want to test it
                        if not category_filter:
                            category_filter = ft_res.category if ft_res.category_confidence >= args.confidence_threshold else None

                # Retrieval logic (using existing functions)
                if not args.use_expansion and not args.use_reranker and not args.use_hybrid and not classifier and not args.use_fasttext:
                    output = await retrieve_context(question, top_k=top_k_retrieval, category_filter=category_filter)
                    search_type = "Simple"
                else:
                    output = await retrieve_context_expanded(
                        question, 
                        top_k_retrieval=top_k_retrieval,
                        top_k_rerank=top_k_rerank,
                        use_expansion=args.use_expansion,
                        use_hybrid=args.use_hybrid,
                        confidence_threshold=args.confidence_threshold,
                        category_filter=category_filter
                    )
                    search_type = "Advanced"
                
                # Metrics
                curr_k = top_k_rerank if top_k_rerank else top_k_retrieval
                metrics = evaluator.calculate_metrics(expected_chunks, output.docs, output.scores, top_k=curr_k)
                
                # Log to trace
                trace.update(
                    input={"question": question},
                    output={"docs": output.docs, "metrics": metrics},
                    metadata={
                        "expansion": args.use_expansion,
                        "hybrid": args.use_hybrid,
                        "reranker": args.use_reranker,
                        "search_type": search_type,
                        "category_filter": category_filter,
                    }
                )
                
                for m_name, m_val in metrics.items():
                    trace.score(name=m_name, value=float(m_val))
                
                all_metrics.append(metrics)
                print(f"[{search_type}] Hit: {metrics['hit_rate']:.2f} | MRR: {metrics['mrr']:.2f}")

            except Exception as e:
                print(f"⚠️ Error: {e}")
                continue

    # Final Classification Summary
    if all_metrics:
        print("\n🏁 BENCHMARK SUMMARY")
        avg_hit = sum(m["hit_rate"] for m in all_metrics) / len(all_metrics)
        avg_mrr = sum(m["mrr"] for m in all_metrics) / len(all_metrics)
        print(f"  - Avg Hit: {avg_hit:.4f}")
        print(f"  - Avg MRR: {avg_mrr:.4f}")

        # Classification Metrics Report
        for tag, eval_obj in [("zs", cls_evaluator), ("ft", ft_evaluator)]:
            if cls_results[tag]["true"] and cls_results[tag]["pred"]:
                metrics = eval_obj.calculate_metrics(
                    cls_results[tag]["true"], 
                    cls_results[tag]["pred"],
                    cls_results[tag]["conf"]
                )
                
                label = "Zero-Shot" if tag == "zs" else "FastText"
                print(f"\n📊 {label} Performance:")
                for k, v in metrics.items():
                    print(f"  - {k.replace('_', ' ').title()}: {v:.4f}")
                    langfuse.score(name=f"{tag}_{k}", value=v)

import json

if __name__ == "__main__":
    # Load config from JSON if exists
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_modular_config.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    # Extract nodes enablement
    nodes_enabled = {node["name"]: node.get("enabled", False) for node in config.get("nodes", [])}
    
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="?", default=config.get("dataset"), help="Dataset name")
    parser.add_argument("--use_expansion", action="store_true", default=nodes_enabled.get("expand_query", False))
    parser.add_argument("--use_hybrid", action="store_true", default=nodes_enabled.get("hybrid_search", False))
    parser.add_argument("--use_classifier", action="store_true", default=nodes_enabled.get("classify", False))
    parser.add_argument("--use_fasttext", action="store_true", default=nodes_enabled.get("fasttext_classify", False))
    parser.add_argument("--use_reranker", action="store_true", default=nodes_enabled.get("rerank", False))
    parser.add_argument("--top_k_retrieval", type=int, default=config.get("top_k_retrieval", 10))
    parser.add_argument("--top_k_rerank", type=int, default=config.get("top_k_rerank", 5))
    parser.add_argument("--confidence_threshold", type=float, default=config.get("confidence_threshold", 0.5))
    
    args = parser.parse_args()

    if not args.dataset:
        print("❌ Error: Dataset name is required (either in bench_modular_config.json or as argument)")
        sys.exit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_modular_bench(args))
