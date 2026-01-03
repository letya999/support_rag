from typing import Dict, Any, List
from .complexity_detector import ComplexityDetector
from .hop_resolver import HopResolver
from .relation_graph import RelationGraphBuilder
from .context_merger import ContextMerger
from app.observability.tracing import observe

# Singletons for reusing across requests
_detector = ComplexityDetector()
_relation_builder = RelationGraphBuilder()
_context_merger = ContextMerger()
_resolver = HopResolver(_relation_builder, _context_merger)
_graph_built = False

@observe(as_type="span")
async def multihop_node(state: Dict[str, Any]):
    """
    LangGraph node for Multi-hop reasoning.
    """
    global _graph_built
    
    question = state.get("question", "")
    docs = state.get("docs", [])
    scores = state.get("rerank_scores") or state.get("scores", [])
    
    # In a real app, we'd want best_doc_metadata to be a list or have access to all retrieved metadata
    # For now, let's assume we can reconstruct or we already have what we need.
    # If retrieve_node only returns one metadata, we might need a better way to pass all metadata.
    # Let's assume best_doc_metadata is the metadata of docs[0].
    best_metadata = state.get("best_doc_metadata", {})
    
    # 1. Complexity Detection
    complexity = _detector.detect(question)
    
    # 2. Build graph if needed (only once)
    if not _graph_built:
        await _relation_builder.load_from_db()
        _graph_built = True
        
    # 3. Decision
    if complexity.complexity_level == "simple" or not docs:
        return {
            "complexity_level": complexity.complexity_level,
            "complexity_score": complexity.complexity_score,
            "multihop_used": False,
            "hops_performed": 1,
            "merged_context": docs[0] if docs else ""
        }
    
    # 4. Hop Resolution
    # We pass [best_metadata] as a list for now, assuming primary doc is the focus
    multihop_result = await _resolver.resolve(
        question=question,
        initial_docs=docs,
        initial_scores=scores,
        initial_metadata=[best_metadata],
        num_hops=complexity.num_hops
    )
    
    # 5. Update state
    return {
        "complexity_level": complexity.complexity_level,
        "complexity_score": complexity.complexity_score,
        "primary_doc": multihop_result.primary_doc,
        "related_docs": multihop_result.related_docs,
        "hop_chain": multihop_result.hop_chain,
        "merged_context": multihop_result.merged_context,
        "multihop_used": True,
        "hops_performed": multihop_result.total_hops_performed,
        # We replace docs with the merged context for the generator
        "docs": [multihop_result.merged_context] + multihop_result.related_docs,
        "confidence": multihop_result.confidence
    }
