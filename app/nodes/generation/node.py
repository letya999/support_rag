from typing import Dict, Any, List, Optional
from app.nodes.base_node import BaseNode
from app.integrations.llm import get_llm
from app.observability.tracing import observe
from langchain_core.prompts import ChatPromptTemplate
from app.observability.callbacks import get_langfuse_callback_handler

class GenerationNode(BaseNode):
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        # Load prompts using base class utility
        self.qa_prompt = ChatPromptTemplate.from_template(self._load_prompt("prompt_qa_simple.txt"))
        self.dynamic_human_prompt = self._load_prompt("prompt_qa_dynamic_human.txt")

    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generation node logic.
        """
        # Check if escalation happened - if so, use escalation message instead of generating
        escalation_message = state.get("escalation_message")
        if escalation_message:
            return {"answer": escalation_message}
        
        question = state.get("aggregated_query") or state.get("question")
        docs = state.get("docs", [])
        system_prompt = state.get("system_prompt")
        
        answer = await self._generate_answer(question, docs, system_prompt)
        
        return {"answer": answer}

    async def _generate_answer(self, question: str, docs: List[str], system_prompt: str = None) -> str:
        docs_str = "\n\n".join(docs)
        llm = get_llm()
        
        if system_prompt:
            # Escape curly braces in system_prompt as it may contain data artifacts (like dicts) 
            # that LangChain would otherwise try to interpolate as variables.
            escaped_system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
            chain = ChatPromptTemplate.from_messages([
                ("system", escaped_system_prompt),
                ("human", self.dynamic_human_prompt)
            ]) | llm
            inputs = {"docs": docs_str, "question": question}
        else:
            chain = self.qa_prompt | llm
            inputs = {"docs": docs_str, "question": question}
        
        langfuse_handler = get_langfuse_callback_handler()
        
        response = await chain.ainvoke(
            inputs,
            config={"callbacks": [langfuse_handler]}
        )
        return response.content

# For backward compatibility
generate_node = GenerationNode()

