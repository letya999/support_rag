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

class MultihopNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Multi-hop reasoning logic.
        """
        global _graph_built
        
        question = state.get("question", "")
        docs = state.get("docs", [])
        scores = state.get("rerank_scores") or state.get("scores", [])
        best_metadata = state.get("best_doc_metadata", {})
        
        # 1. Complexity Detection
        complexity = _detector.detect(question)
        
        # 2. Build graph if needed
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
            "docs": [multihop_result.merged_context] + multihop_result.related_docs,
            "confidence": multihop_result.confidence
        }

# For backward compatibility
multihop_node = MultihopNode()
