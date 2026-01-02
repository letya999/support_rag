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
    print(f"   Classifier:{'ON' if args.use_classifier else 'OFF'}")
    print(f"   Reranker:  {'ON' if args.use_reranker else 'OFF'} (k={top_k_rerank})")

    classifier = ClassificationService() if args.use_classifier else None
    input_tokens = 0 # Placeholder if we wanted to track cost


    if not langfuse:
        print("❌ Langfuse client not initialized.")
        return
        
    dataset = langfuse.get_dataset(dataset_name)
    run_name = f"mod-bench-{datetime.now().strftime('%m%d-%H%M')}"
    
    all_metrics = []
    
    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        
        print(f"[{i}/{len(dataset.items)}] {question[:40]}...", end=" ", flush=True)
        
        with item.run(run_name=run_name) as trace:
            try:
                # Classification
                category_filter = None
                pred_category = None
                is_correct_category = None
                
                if classifier:
                    cls_res = await classifier.classify(question)
                    pred_category = cls_res.category
                    category_filter = pred_category if cls_res.category_confidence >= args.confidence_threshold else None
                    
                    # Check ground truth if available in item.metadata
                    # Assuming dataset item stores "category" in metadata
                    gt_category = item.metadata.get("category") if item.metadata else None
                    if gt_category:
                        is_correct_category = (pred_category == gt_category)

                # В зависимости от флагов вызываем разные методы
                if not args.use_expansion and not args.use_reranker and not args.use_hybrid and not classifier:
                    # Simple retrieval
                    output = await retrieve_context(question, top_k=top_k_retrieval, category_filter=category_filter)
                    search_type = "Simple"
                else:
                    # Advanced retrieval
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
                
                if is_correct_category is not None:
                    metrics["class_acc"] = 1.0 if is_correct_category else 0.0

                
                # Log to trace
                trace.update(
                    input={"question": question},
                    output={"docs": output.docs, "metrics": metrics},
                    metadata={
                        "expansion": args.use_expansion,
                        "hybrid": args.use_hybrid,
                        "reranker": args.use_reranker,
                        "top_k_retrieval": top_k_retrieval,
                        "top_k_rerank": top_k_rerank,
                        "search_type": search_type,
                        "pred_category": pred_category,
                        "category_filter": category_filter,
                        "class_acc": metrics.get("class_acc")
                    }
                )
                
                for m_name, m_val in metrics.items():
                    trace.score(name=m_name, value=float(m_val))
                
                all_metrics.append(metrics)
                cls_msg = f" | Cls: {metrics['class_acc']:.0f}" if "class_acc" in metrics else ""
                print(f"[{search_type}] Hit: {metrics['hit_rate']:.2f} | MRR: {metrics['mrr']:.2f}{cls_msg}")

            except Exception as e:
                print(f"⚠️ Error: {e}")
                continue

    if all_metrics:
        avg_hit = sum(m["hit_rate"] for m in all_metrics) / len(all_metrics)
        avg_mrr = sum(m["mrr"] for m in all_metrics) / len(all_metrics)
        avg_cls = sum(m.get("class_acc", 0) for m in all_metrics) / len(all_metrics) if args.use_classifier else 0
        print(f"\n✅ Done! Avg Hit: {avg_hit:.4f}, Avg MRR: {avg_mrr:.4f}, Avg Cls Acc: {avg_cls:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="Dataset name")
    parser.add_argument("--use_expansion", action="store_true", help="Enable Query Expansion")
    parser.add_argument("--use_hybrid", action="store_true", help="Enable Hybrid Search (Vector + BM25)")
    parser.add_argument("--use_classifier", action="store_true", help="Enable Intent Classification & Filtering")
    parser.add_argument("--use_reranker", action="store_true", help="Enable Reranking")
    parser.add_argument("--top_k_retrieval", type=int, default=10)
    parser.add_argument("--top_k_rerank", type=int, default=5)
    parser.add_argument("--confidence_threshold", type=float, default=0.5)
    
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_modular_bench(args))
