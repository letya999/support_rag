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
from app.nodes.generation.evaluator import evaluator as gen_evaluator
from app.nodes.retrieval.evaluator import evaluator as ret_evaluator

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

async def run_generation_bench(args):
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

    print(f"🚀 Starting Generation Benchmark: {dataset_name} (top_k={top_k})")
    
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
    run_name = f"generation-{dataset_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    all_metrics = []
    
    print(f"\n📊 Evaluating {len(dataset.items)} items...\n")

    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        expected_answer = item.expected_output.get("expected_answer", "")

        print(f"[{i}/{len(dataset.items)}] {question[:50]}...", end=" ", flush=True)
        
        # Link this run to the dataset item
        with item.run(run_name=run_name) as trace:
            try:
                # 3. Invoke Pipeline (Retrieve + Generate)
                # evaluate_single calls retrieve_context internally
                eval_res = await gen_evaluator.evaluate_single(question, top_k=top_k)
                
                generated_answer = eval_res["answer"]
                retrieved_docs = eval_res["docs"]
                gen_metrics = eval_res["metrics"] # faithfulness, relevancy

                # 4. Calculate Retrieval Metrics
                # We need scores for some existing metrics, but evaluate_single returns docs list only?
                # Check generation/evaluator.py: evaluate_single returns 'docs' as list of strings.
                # To get scores, we might need to modify generation/evaluator to return scores or 
                # just assume scores are 1.0/descending if not available, OR modify the RetrievalEvaluator to handle missing scores.
                # However, RetrievalEvaluator expects scores.
                # Let's verify existing generation evaluator.
                # It calls `retrieve_context` which returns `RetrievalOutput` (docs, scores).
                # But `evaluate_single` in generation/invoker returns a dict with `docs`.
                # We might be missing scores here. 
                # HOWEVER: `gen_evaluator.evaluate_single` returns `metrics` calculated on generation.
                # If we want accurate retrieval metrics, we need the scores. 
                # Let's rely on `retrieved_docs` and pass dummy scores or modify generation evaluator separately?
                # For now, let's pass dummy scores since existing code might not expose them easily without editing `app/nodes/generation/evaluator.py`.
                # Wait, I CAN look at `app/nodes/generation/evaluator.py` again.
                # It returns `{"metrics": ..., "answer": ..., "docs": docs}`.
                # `retrieve_context` returns `RetrievalOutput`.
                # I should just re-implement the pipeline calls here to get full control or modify the return of evaluate_single.
                # Modifying `evaluate_single` in `app/nodes/generation/evaluator.py` is safer.
                # But for this task, I am told to CREATE bench_generation.py. I can just re-implement the calls here using `retrieve_context` and `generate_answer_simple`.
                
                # Check imports in this file:
                # from app.nodes.generation.evaluator import evaluator as gen_evaluator
                # That evaluator encapsulates the logic. 
                # Let's use the underlying functions directly OR accept that we might not have scores for retrieval metrics.
                # actually, `ret_evaluator` needs scores for `AverageScore` and `NDCG`. `HitRate`, `MRR`, `Recall` operate on content/ids usually?
                # looking at `app/nodes/retrieval/metrics.py`: MRR needs rank. Rank is implicit in list order. Scores are needed for `AverageScore`.
                # If I don't have scores, I can't calc 'AverageScore'.
                # Let's peek at `app/nodes/generation/evaluator.py` content again from history.
                # It calls `retrieve_context`, gets `retrieval_output`.
                # It extracts `docs = retrieval_output.docs`.
                # It throws away scores.
                
                # OPTION: modify `app/nodes/generation/evaluator.py` to return scores. This is cleaner.
                # BUT I cannot modify it in this specific `replace_file_content` call.
                # I will bypass `gen_evaluator.evaluate_single` and call steps manually here to get full data.
                
                from app.nodes.retrieval.search import retrieve_context
                from app.nodes.generation.node import generate_answer_simple
                from app.nodes.classification.classifier import ClassificationService
                from app.nodes.easy_classification.fasttext_classifier import FastTextClassificationService
                from app.nodes.classification.evaluator import evaluator as cls_evaluator
                from app.nodes.easy_classification.evaluator import evaluator as ft_evaluator
                
                # Step 3a: Aggregation (New Step)
                # We need to simulate a state object for aggregation
                from app.nodes.aggregation.node import aggregate_node
                from app.nodes.aggregation.metrics.evaluator import evaluator as agg_evaluator
                
                # Mock history? For single-turn benchmarks, history is usually empty,
                # so aggregation might not do much unless we fake history.
                # But let's run it anyway to see if 'keyword extraction' triggers on context-dependent queries.
                
                # Create a mock state
                mock_state = {
                    "question": question,
                    "session_history": [], # Empty history for now in benchmarks unless dataset provides it
                    "conversation_config": {}
                }
                
                # Run aggregation
                agg_res = await aggregate_node(mock_state)
                # Note: aggregate_node might be sync or async, but we defined it as async def wrapper.
                
                aggregated_query = agg_res.get("aggregated_query", question)
                extracted_entities = agg_res.get("extracted_entities", {})
                
                # Calculate Aggregation Metrics
                agg_metrics = agg_evaluator.calculate_metrics(
                    original_question=question,
                    aggregated_query=aggregated_query,
                    extracted_entities=extracted_entities
                )
                
                # Step 3b: Classification (Using aggregated query? Or original? Pipeline uses aggregated)
                cls_service = ClassificationService()
                ft_service = FastTextClassificationService()
                
                # Use aggregated query for classification if that's what pipeline does
                query_to_use = aggregated_query
                
                cls_res = await cls_service.classify(query_to_use)
                ft_res = await ft_service.classify(query_to_use)
                
                gt_category = item.metadata.get("category") if item.metadata else None
                
                # Step 3c: Retrieve (Using aggregated query)
                ret_output = await retrieve_context(query_to_use, top_k=top_k)
                retrieved_docs = ret_output.docs
                retrieved_scores = ret_output.scores
                
                # Step 3d: Generate (Using aggregated query)
                generated_answer = await generate_answer_simple(query_to_use, retrieved_docs)
                
                # Step 3e: Generation Metrics
                gen_metrics = gen_evaluator.calculate_metrics(
                    question=query_to_use, # Eval against what was actually asked? Or original?
                    # Typically we evaluate relevance against the user's ORIGINAL intent (question).
                    # But if query changed significantly, faithfulness might vary.
                    # Let's use ORIGINAL question for faithfulness check relative to answer?
                    # Or usage of context.
                    # Ragas usually wants the 'question' that prompted the answer.
                    context="\n\n".join(retrieved_docs),
                    answer=generated_answer
                )
                
                # Step 3f: Retrieval Metrics
                ret_metrics = ret_evaluator.calculate_metrics(
                    expected_answer=expected_chunks,
                    retrieved_docs=retrieved_docs,
                    retrieved_scores=retrieved_scores,
                    top_k=top_k
                )
                
                # Combine
                all_single_metrics = {**gen_metrics, **ret_metrics, **agg_metrics}
                
                # Log classification accuracy to trace if GT is available
                if gt_category:
                    # Use evaluators for consistency, even for single items
                    zs_m = cls_evaluator.calculate_metrics([gt_category], [cls_res.category])
                    all_single_metrics["zs_acc"] = zs_m["accuracy"]
                    
                    if ft_res:
                        ft_m = ft_evaluator.calculate_metrics([gt_category], [ft_res.category])
                        all_single_metrics["ft_acc"] = ft_m["accuracy"]

                # 5. Log results to Trace
                trace.update(
                    input={"question": question},
                    output={
                        "answer": generated_answer, 
                        "retrieved_docs": retrieved_docs,
                        "metrics": all_single_metrics,
                        "aggregation": {
                            "aggregated_query": aggregated_query,
                            "entities": extracted_entities
                        },
                        "classification": {
                            "zero_shot": cls_res.category,
                            "fasttext": ft_res.category if ft_res else "N/A"
                        }
                    },
                    metadata={
                        "gt_category": gt_category
                    }
                )
                
                # Create scores in Langfuse
                for m_name, m_val in all_single_metrics.items():
                    trace.score(
                        name=m_name,
                        value=float(m_val)
                    )
                
                all_metrics.append(all_single_metrics)
                
                # Print short summary
                cls_info = f" | Cls: {all_single_metrics.get('zs_acc', 0):.0f}/{all_single_metrics.get('ft_acc', 0):.0f}" if gt_category else ""
                print(f"Hit: {ret_metrics.get('hit_rate', 0):.2f} Gen Faith: {gen_metrics.get('faithfulness', 0):.2f}{cls_info}")

            except Exception as e:
                print(f"⚠️ Error processing item: {e}")
                import traceback
                traceback.print_exc()
                continue

    # 6. Aggregate results (Retrieval + Generation)
    if all_metrics:
        keys = all_metrics[0].keys()
        agg = {k: sum(m[k] for m in all_metrics if k in m) / len(all_metrics) for k in keys}
        
        print(f"\n{'='*40}")
        print(f"🏁 BENCHMARK SUMMARY")
        print(f"{'='*40}")
        print(f"Dataset:            {dataset_name}")
        for k, v in agg.items():
            print(f"{k.replace('_', ' ').title().ljust(20)}: {v:.4f}")
        print(f"{'='*40}")

    langfuse.flush()
    print(f"\n✅ Done! Check Langfuse dataset '{dataset_name}' → run '{run_name}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run generation benchmark on a dataset.")
    parser.add_argument("dataset", help="Name of the dataset file in 'datasets/' (e.g., ground_truth_dataset)")
    parser.add_argument("--top_k", type=int, default=3, help="Number of documents to retrieve (default: 3)")
    
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_generation_bench(args))
