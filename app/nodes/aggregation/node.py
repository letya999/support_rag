from typing import Dict, Any, List
from app.config.conversation_config import conversation_config
from app.nodes.aggregation.lightweight import lightweight_aggregation_node
from app.nodes.aggregation.llm import llm_aggregation_node
from app.pipeline.state import State
from app.observability.tracing import observe

@observe(as_type="span")
async def aggregate_node(state: State) -> Dict[str, Any]:
    """
    Dispatcher node for aggregation.
    Routes to the configured aggregation implementation.
    """
    if conversation_config.use_llm_aggregation:
        return await llm_aggregation_node(state)
    else:
        # Lightweight is synchronous, but we wrap it in async if needed by graph,
        # though graph handles sync/async nodes usually. 
        # But let's make it awaitable compatible if needed or just return direct result.
        # Since `llm_aggregation_node` is async, we should probably make this wrapper async.
        # However, `lightweight_aggregation_node` is sync.
        
        # Checking `lightweight.py`: `def lightweight_aggregation_node(state: State) -> Dict[str, Any]:` (Sync)
        # Checking `llm.py`: `async def llm_aggregation_node(state: State) -> Dict[str, Any]:` (Async)
        
        # We can just return the result directly.
        return lightweight_aggregation_node(state)
