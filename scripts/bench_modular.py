import os
import sys
import asyncio
import argparse
import json
import yaml
from datetime import datetime
from typing import Dict, Any, List

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# --- Auto-fix URLs for local execution (outside Docker) ---
def _fix_local_urls():
    if os.environ.get("REDIS_URL") == "redis://redis:6379/0":
        os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    if os.environ.get("QDRANT_URL") == "http://qdrant:6333":
        os.environ["QDRANT_URL"] = "http://localhost:6333"
    # Also check if they are missing and use defaults from settings if they are docker-names
    from app.settings import settings
    if "redis:6379" in settings.REDIS_URL and not os.path.exists("/.dockerenv"):
        os.environ["REDIS_URL"] = settings.REDIS_URL.replace("redis:6379", "localhost:6379")
    if "qdrant:6333" in settings.QDRANT_URL and not os.path.exists("/.dockerenv"):
        os.environ["QDRANT_URL"] = settings.QDRANT_URL.replace("qdrant:6333", "localhost:6333")

_fix_local_urls()

from app.observability.langfuse_client import get_langfuse_client
from app.observability.callbacks import get_langfuse_callback_handler
from app.nodes.retrieval.evaluator import evaluator
# ... (rest of imports)

from app.nodes.classification.evaluator import evaluator as cls_evaluator
from app.nodes.easy_classification.evaluator import evaluator as ft_evaluator
from app.nodes.prompt_routing.evaluator import evaluator as pr_evaluator
from app.nodes.generation.evaluator import evaluator as gen_evaluator
from app.nodes.dialog_analysis.evaluator import evaluator as da_evaluator

# Import all node instances
from app.nodes.session_starter.node import load_session_node
from app.nodes.input_guardrails.node import input_guardrails_node
from app.nodes.check_cache.node import check_cache_node
from app.nodes.store_in_cache.node import store_in_cache_node
from app.nodes.language_detection.node import language_detection_node
from app.nodes.dialog_analysis.node import dialog_analysis_node
from app.nodes.state_machine.node import state_machine_node
from app.nodes.aggregation.node import aggregate_node
from app.nodes.query_translation.node import query_translation_node
from app.nodes.easy_classification.node import fasttext_classify_node
from app.nodes.classification.node import classify_node
from app.nodes.metadata_filtering.node import metadata_filter_node
from app.nodes.query_expansion.node import query_expansion_node
from app.nodes.hybrid_search.node import hybrid_search_node
from app.nodes.retrieval.node import retrieve_node
from app.nodes.lexical_search.node import lexical_node
from app.nodes.fusion.node import fusion_node
from app.nodes.reranking.node import rerank_node
from app.nodes.routing.node import route_node
from app.nodes.prompt_routing.node import route_prompt_node
from app.nodes.generation.node import generate_node
from app.nodes.output_guardrails.node import output_guardrails_node
from app.nodes.archive_session.node import archive_session_node
from app.nodes.cache_similarity.node import cache_similarity_node

# Optional: multihop
try:
    from app.nodes.multihop.node import multihop_node
except ImportError:
    multihop_node = None

langfuse = get_langfuse_client()

# Mapping from benchmark config names to pipeline order names
CONFIG_TO_ORDER_MAP = {
    "load_session": "session_starter",
    "fasttext_classify": "easy_classification",
    "rerank": "reranking",
    "analyze_dialog": "dialog_analysis",
    # Others match 1:1
}

# Mapping from order names to node instances
NODE_INSTANCES = {
    "session_starter": load_session_node,
    "input_guardrails": input_guardrails_node,
    "check_cache": check_cache_node,
    "cache_similarity": cache_similarity_node,
    "language_detection": language_detection_node,
    "dialog_analysis": dialog_analysis_node,
    "state_machine": state_machine_node,
    "aggregation": aggregate_node,
    "query_translation": query_translation_node,
    "easy_classification": fasttext_classify_node,
    "classify": classify_node,
    "metadata_filtering": metadata_filter_node,
    "expand_query": query_expansion_node,
    "hybrid_search": hybrid_search_node,
    "retrieve": retrieve_node,
    "lexical_search": lexical_node,
    "fusion": fusion_node,
    "reranking": rerank_node,
    "multihop": multihop_node,
    "routing": route_node,
    "prompt_routing": route_prompt_node,
    "generation": generate_node,
    "output_guardrails": output_guardrails_node,
    "archive_session": archive_session_node,
    "store_in_cache": store_in_cache_node,
}

def get_pipeline_order() -> List[str]:
    """Load the canonical execution order from pipeline_order.yaml."""
    order_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "pipeline", "pipeline_order.yaml")
    if os.path.exists(order_path):
        with open(order_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("pipeline_order", [])
    return list(NODE_INSTANCES.keys()) # Fallback

async def run_modular_bench(args, config):
    dataset_name = args.dataset
    if dataset_name.endswith(".json"):
        dataset_name = dataset_name[:-5]
    
    # Determine which nodes are enabled
    # Priority: CLI args (if set) > config.json
    cli_overrides = {
        "expand_query": args.use_expansion,
        "hybrid_search": args.use_hybrid,
        "classify": args.use_classifier,
        "easy_classification": args.use_fasttext, # note: mapping handled in parser default
        "reranking": args.use_reranker,
        "session_starter": args.use_session_loader,
        "dialog_analysis": args.use_dialog_analysis,
        "prompt_routing": args.use_prompt_routing,
        "cache_similarity": args.use_cache_similarity,
    }
    
    # Initialize enabled set from config.json
    enabled_nodes = set()
    for node_cfg in config.get("nodes", []):
        name = node_cfg.get("name")
        # Map bench name to order name
        order_name = CONFIG_TO_ORDER_MAP.get(name, name)
        if node_cfg.get("enabled"):
            enabled_nodes.add(order_name)
            
    # Apply CLI overrides
    # If a CLI flag is explicitly provided (default is from config), it takes precedence.
    # But argparse 'default' already takes it from config, so we just check them all.
    for name, enabled in cli_overrides.items():
        if enabled:
            enabled_nodes.add(name)
        elif name in enabled_nodes and not enabled:
            # Handle the case where CLI might want to disable something enabled in config?
            # Argparse action_store_true doesn't easily support disabling unless we add --no-X.
            # For now, we assume if it's False in CLI but True in config, and CLI was default, we keep True.
            pass

    pipeline_order = get_pipeline_order()
    active_sequence = [node for node in pipeline_order if node in enabled_nodes]

    print(f"🚀 Modular Benchmark: {dataset_name}")
    print(f"   Active Nodes: {', '.join(active_sequence)}")
    
    search_type = "Advanced" if any(n in enabled_nodes for n in ["hybrid_search", "reranking", "expand_query"]) else "Simple"

    if not langfuse:
        print("❌ Langfuse client not initialized.")
        return
        
    try:
        dataset = langfuse.get_dataset(dataset_name)
    except Exception as e:
        print(f"❌ Error fetching dataset: {e}")
        return

    run_name = f"mod-bench-{datetime.now().strftime('%m%d-%H%M')}"
    
    all_metrics = []
    cls_results = {"zs": {"true": [], "pred": [], "conf": []}, "ft": {"true": [], "pred": [], "conf": []}}
    selected_prompts_list = []
    
    for i, item in enumerate(dataset.items, 1):
        question = item.input["question"]
        expected_chunks = item.expected_output.get("expected_chunks", [])
        gt_category = item.metadata.get("category") if item.metadata else None
        
        print(f"[{i}/{len(dataset.items)}] {question[:40]}...", end=" ", flush=True)
        
        with item.run(run_name=run_name) as trace:
            try:
                # Create a handler linked to this specific trace
                try:
                    from langfuse.langchain import CallbackHandler
                    # Attempt to link using trace_id and observation_id (parent)
                    # trace.id is the current span's ID
                    lf_handler = CallbackHandler(
                        trace_id=trace.trace_id,
                        observation_id=trace.id
                    )
                except Exception:
                    # Fallback to unlinked handler
                    from langfuse.langchain import CallbackHandler
                    lf_handler = CallbackHandler()

                state = {
                    "question": question, 
                    "user_id": "bench_user",
                    "session_id": f"bench_session_{i}",
                    "docs": [], 
                    "answer": "", 
                    "confidence": 0.0,
                    "conversation_history": [],
                    "langfuse_handler": lf_handler # Pass handler to nodes
                }

                # Execution Loop following pipeline_order
                import io
                import contextlib
                
                skip_to_node = None
                nodes_actually_executed = []

                for node_name in pipeline_order:
                    # Handle skipping
                    if skip_to_node:
                        if node_name == skip_to_node:
                            skip_to_node = None
                        else:
                            continue
                    
                    if node_name not in enabled_nodes:
                        continue
                    
                    node_inst = NODE_INSTANCES.get(node_name)
                    if not node_inst:
                        continue
                    
                    nodes_actually_executed.append(node_name)
                    
                    # Execute node
                    if not args.verbose:
                        with contextlib.redirect_stdout(io.StringIO()):
                            updates = await node_inst(state)
                    else:
                        updates = await node_inst(state)

                    if updates:
                        state.update(updates)
                    
                    # --- BRANCHING LOGIC (Synced with graph.py) ---
                    
                    # 1. Guardrails Block → Skip to state_machine
                    if node_name == "input_guardrails" and state.get("guardrails_blocked"):
                        if "state_machine" in enabled_nodes:
                            skip_to_node = "state_machine"
                            continue
                    
                    # 2. Cache Hit → Skip to store_in_cache
                    if node_name in ["check_cache", "cache_similarity"] and state.get("cache_hit"):
                        if "store_in_cache" in enabled_nodes:
                            skip_to_node = "store_in_cache"
                            continue
                        else:
                            break # Done
                            
                    # 3. Dialog Analysis Early Exit (Fast Escalate)
                    if node_name == "dialog_analysis":
                        if state.get("safety_violation") or state.get("escalation_requested"):
                            if "state_machine" in enabled_nodes:
                                skip_to_node = "state_machine"
                                continue
                            
                    # 4. Routing Decision → Skip generation if not auto_reply
                    if node_name == "routing":
                        if state.get("action") != "auto_reply":
                            # Skip to archive or store or end
                            if "archive_session" in enabled_nodes:
                                skip_to_node = "archive_session"
                            elif "store_in_cache" in enabled_nodes:
                                skip_to_node = "store_in_cache"
                            else:
                                break
                            continue

                # Retrieval Results
                output_docs = state.get("docs", [])
                output_scores = state.get("rerank_scores") or state.get("scores") or [0.0] * len(output_docs)
                
                # Metrics Calculation
                # Use top_k from args or inferred from config
                curr_k = args.top_k_rerank if "reranking" in enabled_nodes else args.top_k_retrieval
                metrics = evaluator.calculate_metrics(expected_chunks, output_docs, output_scores, top_k=curr_k)
                
                # Distribution analysis for summary
                if "classify" in enabled_nodes:
                    pred = state.get("category")
                    conf = state.get("category_confidence")
                    if pred and gt_category:
                        cls_results["zs"]["pred"].append(pred)
                        cls_results["zs"]["conf"].append(conf or 0.0)
                        cls_results["zs"]["true"].append(gt_category)

                if "easy_classification" in enabled_nodes:
                    pred = state.get("semantic_category")
                    conf = state.get("semantic_category_confidence")
                    if pred and gt_category:
                        cls_results["ft"]["pred"].append(pred)
                        cls_results["ft"]["conf"].append(conf or 0.0)
                        cls_results["ft"]["true"].append(gt_category)

                if "prompt_routing" in enabled_nodes:
                    selected_prompt_key = state.get("dialog_state", "DEFAULT")
                    selected_prompts_list.append(selected_prompt_key)

                # Log to trace
                trace.update(
                    input={"question": question},
                    output={"docs": output_docs, "metrics": metrics, "answer": state.get("answer")},
                    metadata={
                        "search_type": search_type,
                        "cache_hit": state.get("cache_hit", False),
                        "nodes_executed": nodes_actually_executed,
                        "category_filter": state.get("matched_category"),
                        "selected_prompt": state.get("dialog_state") if "prompt_routing" in enabled_nodes else "N/A"
                    }
                )
                
                for m_name, m_val in metrics.items():
                    trace.score(name=m_name, value=float(m_val))
                
                # Generation Metrics
                if "generation" in enabled_nodes and state.get("answer"):
                    try:
                        gen_metrics = gen_evaluator.calculate_metrics(state)
                        for m_name, m_val in gen_metrics.items():
                            trace.score(name=f"gen_{m_name}", value=float(m_val))
                    except Exception as e:
                        print(f"⚠️ Generation metrics error: {e}")
                
                # Dialog Analysis Metrics
                if "dialog_analysis" in enabled_nodes and state.get("dialog_analysis"):
                    try:
                        da_metrics = da_evaluator.calculate_metrics(state)
                        for m_name, m_val in da_metrics.items():
                            trace.score(name=f"da_{m_name}", value=float(m_val))
                    except Exception as e:
                        print(f"⚠️ Dialog analysis metrics error: {e}")
                
                all_metrics.append(metrics)
                if args.verbose:
                    print(f"[{search_type}] Hit: {metrics['hit_rate']:.2f} | MRR: {metrics['mrr']:.2f}")
                else:
                    print("✅")

            except Exception as e:
                print(f"⚠️ Error: {e}")
                import traceback
                traceback.print_exc()
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
                try:
                    metrics = eval_obj.calculate_metrics(
                        cls_results[tag]["true"], 
                        cls_results[tag]["pred"],
                        cls_results[tag]["conf"]
                    )
                    
                    label = "Zero-Shot (classify)" if tag == "zs" else "FastText (easy_classification)"
                    print(f"\n📊 {label} Performance:")
                    for k, v in metrics.items():
                        print(f"  - {k.replace('_', ' ').title()}: {v:.4f}")
                except Exception as e:
                    print(f"⚠️ Metric evaluation error: {e}")
        
        # Prompt Routing Distribution
        if "prompt_routing" in enabled_nodes and selected_prompts_list:
            dist = pr_evaluator.analyze_distribution(selected_prompts_list)
            print(f"\n🎭 Prompt Routing Distribution:")
            for k, v in dist.items():
                print(f"  - {k}: {v:.2%}")

if __name__ == "__main__":
    # Load config from JSON if exists
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_modular_config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading bench_modular_config.json: {e}")
    
    if "nodes" not in config:
        config["nodes"] = []

    def get_enabled_default(name):
        """Find enabled status for a node in bench_modular_config.json."""
        for n in config.get("nodes", []):
            if n["name"] == name:
                return n.get("enabled", False)
        return False

    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="?", default=config.get("dataset"), help="Dataset name")
    
    # Map the CLI names back to config names or order names
    parser.add_argument("--use_expansion", action="store_true", default=get_enabled_default("expand_query"))
    parser.add_argument("--use_hybrid", action="store_true", default=get_enabled_default("hybrid_search"))
    parser.add_argument("--use_classifier", action="store_true", default=get_enabled_default("classify"))
    parser.add_argument("--use_fasttext", action="store_true", default=get_enabled_default("fasttext_classify"))
    parser.add_argument("--use_reranker", action="store_true", default=get_enabled_default("rerank"))
    parser.add_argument("--use_session_loader", action="store_true", default=get_enabled_default("load_session"))
    parser.add_argument("--use_dialog_analysis", action="store_true", default=get_enabled_default("analyze_dialog"))
    parser.add_argument("--use_prompt_routing", action="store_true", default=get_enabled_default("prompt_routing"))
    parser.add_argument("--use_cache_similarity", action="store_true", default=get_enabled_default("cache_similarity"))
    
    parser.add_argument("--verbose", action="store_true", help="Show all node logs and detailed results")
    
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
