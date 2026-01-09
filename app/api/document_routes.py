from fastapi import APIRouter, HTTPException, UploadFile, File
from app.observability.tracing import observe
import asyncio
import tempfile
import os
import shutil
from app.services.batch_processors import DocumentBatchProcessor
from app.services.ingestion import DocumentIngestionService
from app.services.document_loaders import ProcessedQAPair

router = APIRouter()

@router.post("/upload", response_model=dict)
@observe()
async def upload_documents(files: list = None):
    """Upload and process documents for Q&A extraction.

    Accepts up to 5 documents in formats: PDF, DOCX, CSV, Markdown.
    Returns extracted Q&A pairs for confirmation before ingestion.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files per upload")

    try:
        # Save uploaded files temporarily
        temp_dir = tempfile.mkdtemp()
        file_paths = []

        for file in files:
            if not file:
                continue

            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
            file_paths.append(file_path)

        # Process batch
        processor = DocumentBatchProcessor()
        result = await processor.process_batch(
            file_paths,
            auto_confirm=False,
            confidence_threshold=0.6,
            skip_duplicates=True
        )

        # Clean up temp files
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Convert result to response format
        return {
            "total_files": result.total_files,
            "processed_files": result.processed_files,
            "failed_files": [
                {
                    "file_name": f.file_name,
                    "error_type": f.error_type,
                    "error_message": f.error_message
                }
                for f in result.failed_files
            ],
            "qa_pairs": [p.to_dict() for p in result.qa_pairs],
            "warnings": result.warnings,
            "summary": result.summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing documents: {str(e)}")


@router.post("/confirm", response_model=dict)
@observe()
async def confirm_upload(request: dict):
    """Confirm and ingest Q&A pairs into the vector store.

    Takes validated Q&A pairs and stores them in PostgreSQL and Qdrant.
    """
    try:
        qa_pairs_data = request.get("qa_pairs", [])

        if not qa_pairs_data:
            raise HTTPException(status_code=400, detail="No Q&A pairs provided")

        # Convert to ProcessedQAPair objects
        pairs = []
        for pair_data in qa_pairs_data:
            pair = ProcessedQAPair(
                question=pair_data.get("question", ""),
                answer=pair_data.get("answer", ""),
                metadata=pair_data.get("metadata", {})
            )
            pairs.append(pair)

        # Ingest to database
        result = await DocumentIngestionService.ingest_pairs(pairs)

        return {
            "status": result["status"],
            "ingested_count": result["ingested_count"],
            "message": f"Successfully ingested {result['ingested_count']} Q&A pairs"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting documents: {str(e)}")
