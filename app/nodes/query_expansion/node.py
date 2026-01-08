from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.query_expansion.expander import QueryExpander
from app.observability.tracing import observe

class QueryExpansionNode(BaseNode):
    """
    Expands user query into multiple related queries.
    
    Contracts:
        Input:
            Required: None
            Optional:
                - question (str): Original question
                - aggregated_query (str): Enhanced query
        
        Output:
            Guaranteed:
                - queries (List[str]): Expanded queries
            Conditional: None
    """
    
    INPUT_CONTRACT = {
        "required": [],
        "optional": ["question", "aggregated_query"]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["queries"],
        "conditional": []
    }
    
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
