from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.integrations.llm import get_llm
from app.pipeline.state import State
from app.observability.tracing import observe
from app.pipeline.config_proxy import conversation_config

from app.nodes.base_node import BaseNode

class LLMAggregator(BaseNode):
    def __init__(self):
        super().__init__()
        self.llm = get_llm(temperature=0.0) # Low temperature for precision
        self.output_parser = StrOutputParser()
        
        # Load prompt using base class utility
        system_prompt = self._load_prompt("prompt_rewriting.txt")
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "History:\n{history}\n\nLatest Question: {question}")
        ])
        
        self.chain = self.prompt | self.llm | self.output_parser

    @observe(as_type="span")
    async def aggregate(self, history: List[str], question: str) -> str:
        history_text = "\n".join(history)
        return await self.chain.ainvoke({"history": history_text, "question": question})

@observe(as_type="span")
async def llm_aggregation_node(state: State) -> Dict[str, Any]:
    """
    LangGraph node for LLM-based Conversation Aggregation.
    """
    question = state.get("question", "")
    history_objs = state.get("conversation_history", []) or []
    
    max_msgs = conversation_config.aggregation_max_messages
    relevant_history = history_objs[-max_msgs:]
    
    # Format history as "Role: Content"
    formatted_history = [
        f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
        for msg in relevant_history
    ]
    
    aggregator = LLMAggregator()
    aggregated_query = await aggregator.aggregate(formatted_history, question)
    
    # We don't extract entities explicitly here as the LLM embeds them in the query,
    # but we could populate extraction if needed later. For now, we leave it empty or reuse lightweight logic if we wanted.
    # The instructions say "LLM Aggregator ... Fallback for cases where lightweight fails".
    
    return {
        "aggregated_query": aggregated_query,
        # We can leave extracted_entities empty or implement a separate LLM extraction if required. 
        # Roadmap says "extracts entities" for lightweight, but for LLM it usually focuses on query rewriting.
        "extracted_entities": {} 
    }
