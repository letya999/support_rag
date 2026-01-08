from typing import Dict, Any, List, Optional
from app.nodes.base_node import BaseNode
from app.integrations.llm import get_llm
from app.observability.tracing import observe
from langchain_core.prompts import ChatPromptTemplate
from app.observability.callbacks import get_langfuse_callback_handler

class GenerationNode(BaseNode):
    """
    Generation node for producing answers using LLM.
    
    Contracts:
        Input:
            Required: None (flexible - uses one of the combinations below)
            Optional:
                - system_prompt (str): Pre-built system prompt from prompt_routing
                - human_prompt (str): Pre-built human prompt
                - docs (List[str]): Retrieved documents for context
                - question (str): User question
                - aggregated_query (str): Aggregated/enhanced query
                - escalation_message (str): If set, skip generation
                - langfuse_handler: Custom callback handler
        
        Output:
            Guaranteed:
                - answer (str): Generated answer
            Conditional: None
    """
    
    INPUT_CONTRACT = {
        "required": [],  # Flexible - can work with different combos
        "optional": [
            "system_prompt",
            "human_prompt", 
            "docs",
            "question",
            "aggregated_query",
            "escalation_message"
        ]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["answer"],
        "conditional": []
    }
    
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        # Load prompts using base class utility
        self.qa_prompt = ChatPromptTemplate.from_template(self._load_prompt("prompt_qa_simple.txt"))
        self.dynamic_human_prompt = self._load_prompt("prompt_qa_dynamic_human.txt")

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generation node logic.

        Contracts:
            - Required Inputs: `system_prompt` OR `docs`+`question` (str)
            - Optional Inputs: `escalation_message` (str), `human_prompt` (str), `aggregated_query` (str)
            - Guaranteed Outputs: `answer` (str)
        """
        # Check if escalation happened - if so, use escalation message instead of generating
        escalation_message = state.get("escalation_message")
        if escalation_message:
            return {"answer": escalation_message}
            
        # Use pre-built prompts from prompt_routing
        system_prompt = state.get("system_prompt")
        human_prompt = state.get("human_prompt")
        
        if not human_prompt:
            # Fallback: build from docs + question
            question = state.get("aggregated_query") or state.get("question")
            docs = state.get("docs", [])
            docs_str = "\n\n".join(docs)
            human_prompt = f"Context:\n{docs_str}\n\nQuestion: {question}"
        
        # Build chain
        if system_prompt:
            # Escape curly braces in system_prompt as it may contain data artifacts
            escaped = system_prompt.replace("{", "{{").replace("}", "}}")
            chain = ChatPromptTemplate.from_messages([
                ("system", escaped),
                ("human", "{human_prompt}")
            ]) | get_llm()
        else:
            chain = self.qa_prompt | get_llm()
        
        # Use handler from state if provided (e.g. from benchmark script), otherwise create new
        langfuse_handler = state.get("langfuse_handler")
        if not langfuse_handler:
            langfuse_handler = get_langfuse_callback_handler()
        
        response = await chain.ainvoke(
            {"human_prompt": human_prompt},
            config={"callbacks": [langfuse_handler]}
        )
        return {"answer": response.content}


# For backward compatibility
generate_node = GenerationNode()


async def generate_answer_simple(question: str, docs: List[str]) -> str:
    """
    Simple generation helper for evaluation/testing.
    Directly generates an answer from question and docs without full pipeline state.
    """
    docs_str = "\n\n".join(docs)
    
    # Reuse the prompt loaded by the main node (avoids reloading file)
    qa_prompt = generate_node.qa_prompt
    chain = qa_prompt | get_llm()
    
    langfuse_handler = get_langfuse_callback_handler()
    
    # prompt_qa_simple.txt expects {docs} and {question}
    response = await chain.ainvoke(
        {"docs": docs_str, "question": question},
        config={"callbacks": [langfuse_handler]}
    )
    return response.content

