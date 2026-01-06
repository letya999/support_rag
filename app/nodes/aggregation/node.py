from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
from app.pipeline.config_proxy import conversation_config
from app.nodes.aggregation.lightweight import lightweight_aggregation_node
from app.nodes.aggregation.llm import llm_aggregation_node
from app.pipeline.state import State
from app.observability.tracing import observe

class AggregationNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatcher for aggregation.
        Routes to the configured aggregation implementation.
        """
        if conversation_config.use_llm_aggregation:
            return await llm_aggregation_node(state)
        else:
            return lightweight_aggregation_node(state)

# For backward compatibility
aggregate_node = AggregationNode()
