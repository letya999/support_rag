from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.query_expansion.expander import QueryExpander
from app.observability.tracing import observe

class QueryExpansionNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query Expansion logic.
        """
        question = state.get("aggregated_query") or state.get("question", "")
        
        expander = QueryExpander()
        expanded_queries = await expander.expand(question)
        
        return {
            "queries": expanded_queries
        }

# For backward compatibility
query_expansion_node = QueryExpansionNode()
