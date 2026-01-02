from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.embeddings import get_embedding
from app.search import search_documents
from langfuse import observe
from langfuse.langchain import CallbackHandler

class State(TypedDict):
    question: str
    docs: List[str]
    answer: str

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
    return {"docs": docs}

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
    # Using specific tagging and context to ensure nesting
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

# Build graph
workflow = StateGraph(State)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

# Compile
rag_graph = workflow.compile()
