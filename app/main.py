from fastapi import FastAPI, Query, HTTPException
import os
from app.utils import get_embedding, search_documents
from langfuse import observe, get_client
from langfuse.decorators import langfuse_context
from app.rag_graph import rag_graph

# Rename to avoid shadowing the 'langfuse' package
langfuse_client = get_client()

app = FastAPI(title="Support RAG API")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "database": "connected" if os.getenv("DATABASE_URL") else "missing",
        "langfuse": "configured" if os.getenv("LANGFUSE_PUBLIC_KEY") else "missing"
    }

@app.get("/")
async def root():
    return {"message": "Support RAG Pipeline API is running"}

@app.get("/search")
@observe()
async def search(q: str = Query(..., description="The search query")):
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Set trace input
    langfuse_client.update_current_trace(
        name="document-search",
        input=q,
        tags=["production" if os.getenv("NODE_ENV") == "production" else "development"]
    )
    
    try:
        embedding = await get_embedding(q)
        results = await search_documents(embedding, top_k=3)
        
        # Set trace output
        langfuse_client.update_current_trace(output=results)
        
        return {
            "query": q,
            "results": results
        }
    except Exception as e:
        langfuse_client.update_current_trace(output=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ask")
@observe()
async def ask(q: str = Query(..., description="Question to answer")):
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Initialize Langfuse Callback Handler linked to the current trace
    # Using get_current_langchain_handler() automatically links to the @observe() trace
    langfuse_handler = langfuse_context.get_current_langchain_handler()

    
    try:
        # Invoke the graph
        result = await rag_graph.ainvoke(
            {"question": q}, 
            config={
                "callbacks": [langfuse_handler],
                "run_name": "rag_pipeline"
            }
        )
        
        return {
            "question": q,
            "answer": result["answer"],
            "context": result["docs"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
