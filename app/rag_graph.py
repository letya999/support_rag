from typing import TypedDict, List, Optional, Literal
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.embeddings import get_embedding
from app.search import search_documents
from app.router import decide_action
from app.settings import DEFAULT_CONFIDENCE_THRESHOLD
from langfuse import observe
from langfuse.langchain import CallbackHandler

class State(TypedDict):
    question: str
    docs: List[str]
    answer: Optional[str]
    action: Optional[Literal["auto_reply", "handoff"]]
    confidence: Optional[float]
    matched_intent: Optional[str]
    matched_category: Optional[str]
    best_doc_metadata: Optional[dict]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

@observe(as_type="span")
async def retrieve(state: State):
    """
    Retrieve documents based on the question.
    """
    question = state["question"]
    # Generate embedding
    embedding = await get_embedding(question)
    # Search in vector store
    results = await search_documents(embedding, top_k=3)
    
    # Extract content
    docs = [r["content"] for r in results]
    
    # Extract top result info
    top_result = results[0] if results else None
    confidence = top_result["score"] if top_result else 0.0
    best_doc_metadata = top_result["metadata"] if top_result else {}
    
    return {
        "docs": docs,
        "confidence": confidence,
        "best_doc_metadata": best_doc_metadata
    }

@observe(as_type="span")
async def route(state: State):
    """
    Decide whether to auto-reply or handoff based on retrieval results.
    """
    metadata = state.get("best_doc_metadata", {})
    confidence = state.get("confidence", 0.0)
    
    requires_handoff = metadata.get("requires_handoff", False)
    threshold = metadata.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
    
    action = decide_action(confidence, requires_handoff, threshold)
    
    return {
        "action": action,
        "matched_intent": metadata.get("intent"),
        "matched_category": metadata.get("category")
    }

@observe(as_type="span")
async def generate(state: State):
    """
    Generate answer based on context.
    """
    question = state["question"]
    docs = state["docs"]
    
    # Format context
    docs_str = "\n\n".join(docs)
    
    # Create prompt
    prompt = ChatPromptTemplate.from_template(
        "Ответь на основе контекста: {docs}\n\nВопрос: {question}"
    )
    
    # Simple chain
    chain = prompt | llm
    
    # v3: CallbackHandler automatically links to the current span
    langfuse_handler = CallbackHandler()
    
    # Invoke
    response = await chain.ainvoke(
        {"docs": docs_str, "question": question},
        config={"callbacks": [langfuse_handler]}
    )
    
    return {"answer": response.content}

def router_logic(state: State):
    """
    Conditional edge logic.
    """
    if state["action"] == "auto_reply":
        return "generate"
    return END

# Build graph
workflow = StateGraph(State)
workflow.add_node("retrieve", retrieve)
workflow.add_node("route", route)
workflow.add_node("generate", generate)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "route")
workflow.add_conditional_edges(
    "route",
    router_logic,
    {
        "generate": "generate",
        END: END
    }
)
workflow.add_edge("generate", END)

# Compile
rag_graph = workflow.compile()
