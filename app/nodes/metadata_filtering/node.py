from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.observability.tracing import observe
from app.nodes.metadata_filtering.filtering import MetadataFilteringService

class MetadataFilteringNode(BaseNode):
    def __init__(self):
        self.service = MetadataFilteringService(confidence_threshold=0.4)

    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute metadata filtering logic using the service.
        """
        # Collect categories and confidences from state
        # In the future, this can be a list if the classifier supports it
        categories = state.get("semantic_category")
        confidences = state.get("semantic_category_confidence", 0.0)
        
        # If classifier provides detailed multiple options:
        # categories = state.get("semantic_categories", state.get("semantic_category"))
        # confidences = state.get("semantic_category_scores", state.get("semantic_category_confidence", 0.0))

        if not categories:
            return {
                "filter_used": False,
                "fallback_triggered": False,
                "filtering_reason": "No categories found in state"
            }

        result = await self.service.determine_filter(categories, confidences)
        
        return {
            "filter_used": result.filter_used,
            "fallback_triggered": result.fallback_triggered,
            "filtering_reason": result.filtering_reason,
            "matched_category": result.category_filter
        }

# Singleton instance for the graph
metadata_filter_node = MetadataFilteringNode()
