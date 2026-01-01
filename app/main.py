from fastapi import FastAPI
import os

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
