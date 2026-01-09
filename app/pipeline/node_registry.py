"""
Node Registry for RAG Pipeline.
"""
from app.nodes.retrieval.node import retrieve_node
from app.nodes.generation.node import generate_node
from app.nodes.routing.node import route_node
from app.nodes.query_expansion.node import query_expansion_node
from app.nodes.reranking.node import rerank_node
from app.nodes.hybrid_search.node import hybrid_search_node
from app.nodes.classification.node import classify_node
from app.nodes.easy_classification.node import fasttext_classify_node
from app.nodes.metadata_filtering.node import metadata_filter_node
from app.nodes.check_cache.node import check_cache_node
from app.nodes.store_in_cache.node import store_in_cache_node
from app.nodes.cache_similarity.node import cache_similarity_node
from app.nodes.session_starter.node import load_session_node
from app.nodes.aggregation.node import aggregate_node
from app.nodes.dialog_analysis.node import dialog_analysis_node
from app.nodes.state_machine.node import state_machine_node
from app.nodes.prompt_routing.node import route_prompt_node
from app.nodes.lexical_search.node import lexical_node
from app.nodes.fusion.node import fusion_node
from app.nodes.archive_session.node import archive_session_node
from app.nodes.language_detection.node import language_detection_node
from app.nodes.query_translation.node import query_translation_node
from app.nodes.input_guardrails.node import input_guardrails_node
from app.nodes.output_guardrails.node import output_guardrails_node

# Optional: Import multihop node if available
try:
    from app.nodes.multihop.node import multihop_node
    MULTIHOP_AVAILABLE = True
except ImportError:
    MULTIHOP_AVAILABLE = False
    multihop_node = None

NODE_FUNCTIONS = {
    "check_cache": check_cache_node,
    "cache_similarity": cache_similarity_node,
    "easy_classification": fasttext_classify_node,
    "classify": classify_node,
    "metadata_filtering": metadata_filter_node,
    "expand_query": query_expansion_node,
    "retrieve": retrieve_node,
    "hybrid_search": hybrid_search_node,
    "reranking": rerank_node,
    "multihop": multihop_node,
    "routing": route_node,
    "generation": generate_node,
    "store_in_cache": store_in_cache_node,
    "session_starter": load_session_node,
    "aggregation": aggregate_node,
    "dialog_analysis": dialog_analysis_node,
    "state_machine": state_machine_node,
    "prompt_routing": route_prompt_node,
    "lexical_search": lexical_node,
    "fusion": fusion_node,
    "archive_session": archive_session_node,
    "language_detection": language_detection_node,
    "query_translation": query_translation_node,
    "input_guardrails": input_guardrails_node,
    "output_guardrails": output_guardrails_node,
}

if MULTIHOP_AVAILABLE:
    NODE_FUNCTIONS["multihop"] = multihop_node
