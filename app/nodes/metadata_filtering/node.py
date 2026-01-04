from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.nodes.metadata_filtering.filtering import MetadataFilteringService

class MetadataFilteringNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        category = state.get("category")
        confidence = state.get("category_confidence", 0.0)
        
        # We use a threshold of 0.5 as requested
        if category and confidence and confidence >= 0.5:
            return {
                "filter_used": True,
                "fallback_triggered": False,
                "filtering_reason": "High confidence category detected",
                "matched_category": category
            }
        else:
            return {
                "filter_used": False,
                "fallback_triggered": False,
                "filtering_reason": "Low confidence or no category"
            }

# For backward compatibility
metadata_filter_node = MetadataFilteringNode()
