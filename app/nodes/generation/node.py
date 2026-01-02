from typing import Dict, Any
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
    question = state.get("question")
    docs = state.get("docs", [])
    
    docs_str = "\n\n".join(docs)
    
    llm = get_llm() # Using defaults
    chain = QA_PROMPT | llm
    
    # Callback for tracing
    langfuse_handler = get_langfuse_callback_handler()
    
    response = await chain.ainvoke(
        {"docs": docs_str, "question": question},
        config={"callbacks": [langfuse_handler]}
    )
    
    return {"answer": response.content}
