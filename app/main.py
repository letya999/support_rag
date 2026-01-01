from fastapi import FastAPI, Query, HTTPException
import os
from app.utils import get_embedding, search_documents
from langfuse import observe, get_client

langfuse = get_client()

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
    langfuse.update_current_trace(
        name="document-search",
        input=q,
        tags=["production" if os.getenv("NODE_ENV") == "production" else "development"]
    )
    
    try:
        embedding = get_embedding(q)
        results = search_documents(embedding, top_k=3)
        
        # Set trace output
        langfuse.update_current_trace(output=results)
        
        return {
            "query": q,
            "results": results
        }
    except Exception as e:
        langfuse.update_current_trace(output=str(e))
        raise HTTPException(status_code=500, detail=str(e))
