from app.pipeline.state import State
from app.nodes.metadata_filtering.filtering import MetadataFilteringService

# Since we don't have the vector store count easily accessible without import cycles or DB connection,
# We will implement the check logic simplistically: 
# If confidence > X, we set filter. 
# The retrieval node will need to handle the "not enough results" fallback if it applies strict filtering.
# HOWEVER, the prompt asks for "Fallback on full search" logic.
# We will set formatting in State, and let Retrieval logic handle the actual query construction.

async def metadata_filter_node(state: State) -> State:
    category = state.get("category")
    confidence = state.get("category_confidence", 0.0)
    
    # We use a threshold of 0.5 as requested
    if category and confidence and confidence >= 0.5:
        return {
            "filter_used": True,
            "fallback_triggered": False,
            "filtering_reason": "High confidence category detected",
            "matched_category": category # Confirming the category to use
        }
    else:
        return {
            "filter_used": False,
            "fallback_triggered": False,  # Not triggered because we didn't try
            "filtering_reason": "Low confidence or no category"
        }
