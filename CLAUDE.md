# Support RAG Pipeline

A typical RAG (Retrieval-Augmented Generation) pipeline for support services, designed to answer strictly based on provided Q&A documents.

## Project Goals
- **Ingestion**: Upload Q&A documents (starting with `.json` format) into a vector store.
- **RAG Pipeline**: Use documents to answer user queries with strict adherence to the source material.
- **Evaluation**: Collect metrics (recall@n, faithfulness) using Langfuse.

## Tech Stack
- **Framework**: `langgraph` for orchestrating the RAG workflow.
- **Vector Store**: `pgvector` (PostgreSQL).
- **LLM**: OpenAI.
- **Monitoring/Eval**: `langfuse`.

## Development Commands
- `pip install -r requirements.txt` - Install dependencies.
- `python ingest.py --file data.json` - Ingest Q&A data.
- `python evaluate_retrieval.py` - Run Ragas retrieval evaluation.
- `uvicorn app.main:app --reload` - Start the FastAPI service.
- `pytest` - Run tests.

## Build Guidelines
- **Development Approach**: Gradual implementation, starting from simple MVP and expanding task by task. 
- **Architecture**: Use Feature-Sliced Design (FSD) approach for organizing the codebase.
- **Groundedness**: Ensure the model answers *only* using the retrieved context. If info is missing, it should say so.
- **Modularity**: Keep ingestion, retrieval, and generation steps separate within the LangGraph nodes.
- **Tracing**: All steps must be traced via Langfuse for performance monitoring and evaluation.
- **Format**: Initially support Q&A JSON format mapping (Question -> Answer).

## Evaluation Metrics (Langfuse & Ragas)
- `context_precision`: Measure how well the retrieved chunks are ranked.
- `context_recall`: Measure if all relevant info is in the retrieved chunks.
- `faithfulness`: Measure if the generated answer is strictly based on the retrieved context.
