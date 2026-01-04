from typing import List, Optional, Union
from app.nodes.metadata_filtering.models import FilteringOutput

class MetadataFilteringService:
    """
    Service for determining if we should restrict retrieval to specific metadata categories.
    """
    def __init__(self, confidence_threshold: float = 0.4):
        self.confidence_threshold = confidence_threshold

    async def determine_filter(
        self, 
        categories: Union[str, List[str]], 
        confidence: Union[float, List[float]]
    ) -> FilteringOutput:
        """
        Logic for selecting categories for filtering.
        Supports single category or multiple categories.
        """
        # Convert to lists for uniform processing
        cat_list = [categories] if isinstance(categories, str) else categories
        conf_list = [confidence] if isinstance(confidence, (float, int)) else confidence

        active_filters = []
        for cat, conf in zip(cat_list, conf_list):
            if cat and conf >= self.confidence_threshold:
                active_filters.append(cat)

        if active_filters:
            # If we have multiple categories, we return them as a list (handled by retrieval)
            # For now FilteringOutput expects a string, we might need a list or join them.
            # Let's return them as a list if there are multiple.
            # We'll update the model if needed, but for now we join or return first.
            return FilteringOutput(
                filter_used=True,
                fallback_triggered=False,
                filtering_reason=f"High confidence categories: {', '.join(active_filters)}",
                category_filter=active_filters[0] if len(active_filters) == 1 else active_filters
            )

        return FilteringOutput(
            filter_used=False,
            fallback_triggered=False,
            filtering_reason="No high confidence categories detected"
        )
