from typing import Dict, Any, List
from app.integrations.llm import get_llm
from app.nodes.generation.prompts import QA_PROMPT
from app.nodes.generation.models import GenerationInput, GenerationOutput
from app.observability.tracing import observe
from app.observability.callbacks import get_langfuse_callback_handler

@observe(as_type="span")
async def generate_node(state: Dict[str, Any]):
    """
    Generation node.
    """
    question = state.get("aggregated_query") or state.get("question")
    docs = state.get("docs", [])
    
    answer = await generate_answer_simple(question, docs)
    
    return {"answer": answer}

async def generate_answer_simple(question: str, docs: List[str]) -> str:
    """
    Simpler version for evaluation.
    """
    docs_str = "\n\n".join(docs)
    
    llm = get_llm() # Using defaults
    chain = QA_PROMPT | llm
    
    # Callback for tracing
    langfuse_handler = get_langfuse_callback_handler()
    
    response = await chain.ainvoke(
        {"docs": docs_str, "question": question},
        config={"callbacks": [langfuse_handler]}
    )
    
    return response.content

