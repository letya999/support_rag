"""
Multi-hop reasoning node.

Performs multi-hop reasoning for complex queries that require
information from multiple documents.
"""
from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
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

# Default config values
DEFAULT_OUTPUT_DOCS_COUNT = 3
DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.8


def _get_params() -> Dict[str, Any]:
    """Get node parameters from centralized config."""
    try:
        from app.services.config_loader.loader import get_node_params
        return get_node_params("multihop")
    except Exception:
        return {}


class MultihopNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Multi-hop reasoning logic.
        Returns multiple documents based on output_docs_count config.
        """
        global _graph_built
        
        # Load params from centralized config
        params = _get_params()
        output_docs_count = params.get("output_docs_count", DEFAULT_OUTPUT_DOCS_COUNT)
        skip_if_high_confidence = params.get("skip_if_high_confidence", True)
        high_confidence_threshold = params.get("high_confidence_threshold", DEFAULT_HIGH_CONFIDENCE_THRESHOLD)
        
        question = state.get("question", "")
        docs = state.get("docs", [])
        scores = state.get("rerank_scores") or state.get("scores", [])
        best_metadata = state.get("best_doc_metadata", {})
        current_confidence = state.get("confidence", 0.0)
        
        # Skip if already high confidence (optimization)
        if skip_if_high_confidence and current_confidence >= high_confidence_threshold:
            # Return top N docs without multi-hop processing
            return {
                "complexity_level": "simple",
                "complexity_score": 0.0,
                "multihop_used": False,
                "hops_performed": 0,
                "merged_context": docs[0] if docs else "",
                "docs": docs[:output_docs_count] if docs else [],
                "confidence": current_confidence
            }
        
        # 1. Complexity Detection
        complexity = _detector.detect(question)
        
        # 2. Build graph if needed
        if not _graph_built:
            await _relation_builder.load_from_db()
            _graph_built = True
            
        # 3. Decision for simple queries
        if complexity.complexity_level == "simple" or not docs:
            # For simple queries, return top N docs without merging
            return {
                "complexity_level": complexity.complexity_level,
                "complexity_score": complexity.complexity_score,
                "multihop_used": False,
                "hops_performed": 1,
                "merged_context": docs[0] if docs else "",
                # FIXED: Return multiple docs instead of just 1
                "docs": docs[:output_docs_count] if docs else []
            }
        
        # 4. Hop Resolution for complex queries
        multihop_result = await _resolver.resolve(
            question=question,
            initial_docs=docs,
            initial_scores=scores,
            initial_metadata=[best_metadata],
            num_hops=complexity.num_hops
        )
        
        # 5. Prepare output docs
        # Merged context + related docs, limited to output_docs_count
        output_docs = [multihop_result.merged_context]
        if multihop_result.related_docs:
            remaining_slots = output_docs_count - 1
            output_docs.extend(multihop_result.related_docs[:remaining_slots])
        
        # Ensure we have at least output_docs_count docs if available
        if len(output_docs) < output_docs_count and len(docs) > len(output_docs):
            # Add more from original docs
            for doc in docs:
                if doc not in output_docs:
                    output_docs.append(doc)
                if len(output_docs) >= output_docs_count:
                    break
        
        # 6. Update state
        return {
            "complexity_level": complexity.complexity_level,
            "complexity_score": complexity.complexity_score,
            "primary_doc": multihop_result.primary_doc,
            "related_docs": multihop_result.related_docs,
            "hop_chain": multihop_result.hop_chain,
            "merged_context": multihop_result.merged_context,
            "multihop_used": True,
            "hops_performed": multihop_result.total_hops_performed,
            # FIXED: Return multiple docs based on config
            "docs": output_docs,
            "confidence": multihop_result.confidence
        }


# For backward compatibility
multihop_node = MultihopNode()
