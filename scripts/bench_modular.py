import os
import sys
import asyncio
import argparse
import json
from datetime import datetime
from typing import Dict, Any

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
from app.cache.nodes import check_cache_node, store_in_cache_node # Cache imports
from app.nodes.session_starter.node import load_session_node # Session starter import

langfuse = get_langfuse_client()

def update_config_from_args(config: Dict[str, Any], args: argparse.Namespace):
    """Update configuration dictionary based on command-line arguments."""
    nodes = config.get("nodes", [])
    node_map = {n["name"]: n for n in nodes}

    # Helper to safe update
    def set_enabled(name, is_enabled):
        if name in node_map:
            node_map[name]["enabled"] = is_enabled
        else:
            config["nodes"].append({"name": name, "enabled": is_enabled})

    set_enabled("expand_query", args.use_expansion)
    set_enabled("hybrid_search", args.use_hybrid)
    set_enabled("classify", args.use_classifier)
    set_enabled("fasttext_classify", args.use_fasttext)
    set_enabled("rerank", args.use_reranker)
    set_enabled("load_session", args.use_session_loader)

    
    return config

async def run_modular_bench(args, config):
    dataset_name = args.dataset
    if dataset_name.endswith(".json"):
        dataset_name = dataset_name[:-5]
    
    # Update config with CLI args overrides
    config = update_config_from_args(config, args)
    
    # top_k settings
    top_k_retrieval = args.top_k_retrieval
    top_k_rerank = args.top_k_rerank if args.use_reranker else None
    
    cache_enabled = config.get("cache", {}).get("enabled", False)

    print(f"🚀 Modular Benchmark: {dataset_name}")
    print(f"   Expansion: {'ON' if args.use_expansion else 'OFF'}")
    print(f"   Hybrid:    {'ON' if args.use_hybrid else 'OFF'}")
    print(f"   Classifier (Zero-Shot): {'ON' if args.use_classifier else 'OFF'}")
    print(f"   Classifier (FastText):  {'ON' if args.use_fasttext else 'OFF'}")
    print(f"   Reranker:  {'ON' if args.use_reranker else 'OFF'} (k={top_k_rerank})")
    print(f"   Cache:     {'ON' if cache_enabled else 'OFF'}")

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
                # Cache Check
                cached_docs = None
                state = {"question": question, "docs": [], "answer": "", "confidence": 0.0}

                # Session Load
                if config.get("nodes", []):
                    # Check if session loader enabled
                    session_loader_enabled = any(n["name"] == "load_session" and n.get("enabled", False) for n in config["nodes"])
                    if session_loader_enabled:
                         # Use mock user_id for benchmark
                         state["user_id"] = "bench_user"
                         state["session_id"] = f"bench_session_{i}"
                         updates = await load_session_node(state)
                         state.update(updates)
                
                if cache_enabled:

                    state = await check_cache_node(state)
                    if state.get("cache_hit"):
                         cached_docs = state.get("docs", [])
                         # Scores are not typically cached in current implementation, assume 1.0 or 0
                         # If we really need scores, we'd need to cache them using custom logic
                         output_docs = cached_docs
                         output_scores = [0.0] * len(cached_docs)
                         search_type = "Cache Hit"
                         
                if not cached_docs:
                    # Proceed with normal pipeline
                    
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

                    # Retrieval logic
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
                    
                    output_docs = output.docs
                    output_scores = output.scores
                    
                    # Store in Cache if enabled
                    if cache_enabled:
                        # Update state with results to store
                        state["docs"] = output.docs
                        state["confidence"] = output.confidence
                        # Mock answer to ensure storage (store_in_cache_node requires non-empty answer)
                        state["answer"] = "Retrieval Benchmark Result"
                        await store_in_cache_node(state)
                
                # Metrics
                curr_k = top_k_rerank if top_k_rerank else top_k_retrieval
                metrics = evaluator.calculate_metrics(expected_chunks, output_docs, output_scores, top_k=curr_k)
                
                # Log to trace
                trace.update(
                    input={"question": question},
                    output={"docs": output_docs, "metrics": metrics},
                    metadata={
                        "expansion": args.use_expansion,
                        "hybrid": args.use_hybrid,
                        "reranker": args.use_reranker,
                        "search_type": search_type,
                        "category_filter": category_filter if not cached_docs else "N/A",
                        "cache_hit": bool(cached_docs)
                    }
                )
                
                for m_name, m_val in metrics.items():
                    trace.score(name=m_name, value=float(m_val))
                
                all_metrics.append(metrics)
                print(f"[{search_type}] Hit: {metrics['hit_rate']:.2f} | MRR: {metrics['mrr']:.2f}")

            except Exception as e:
                print(f"⚠️ Error: {e}")
                # import traceback
                # traceback.print_exc()
                continue

    # Final Summary
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

if __name__ == "__main__":
    # Load config from JSON if exists
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_modular_config.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    # Initialize 'nodes' if not present
    if "nodes" not in config:
        config["nodes"] = []

    # Helper to get enabled defaults
    def get_enabled_default(name):
        for n in config.get("nodes", []):
            if n["name"] == name:
                return n.get("enabled", False)
        return False

    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="?", default=config.get("dataset"), help="Dataset name")
    parser.add_argument("--use_expansion", action="store_true", default=get_enabled_default("expand_query"))
    parser.add_argument("--use_hybrid", action="store_true", default=get_enabled_default("hybrid_search"))
    parser.add_argument("--use_classifier", action="store_true", default=get_enabled_default("classify"))
    parser.add_argument("--use_fasttext", action="store_true", default=get_enabled_default("fasttext_classify"))
    parser.add_argument("--use_reranker", action="store_true", default=get_enabled_default("rerank"))
    parser.add_argument("--use_session_loader", action="store_true", default=get_enabled_default("load_session"))
    parser.add_argument("--top_k_retrieval", type=int, default=config.get("top_k_retrieval", 10))
    parser.add_argument("--top_k_rerank", type=int, default=config.get("top_k_rerank", 5))
    parser.add_argument("--confidence_threshold", type=float, default=config.get("confidence_threshold", 0.5))
    
    args = parser.parse_args()

    if not args.dataset:
        print("❌ Error: Dataset name is required (either in bench_modular_config.json or as argument)")
        sys.exit(1)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_modular_bench(args, config))
