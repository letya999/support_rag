from fastapi import FastAPI, Query, HTTPException
import os
from app.utils import get_embedding, search_documents

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
async def search(q: str = Query(..., description="The search query")):
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        embedding = get_embedding(q)
        results = search_documents(embedding, top_k=3)
        return {
            "query": q,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
