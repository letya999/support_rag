from typing import List, Optional, Any, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel, Field
import os
import json
import logging
from langfuse import Langfuse

from app.services.dataset_generation.generator import DatasetGenerator
from app.dataset.schema import EvalItem
from app.dataset.loader import validate_dataset, sync_dataset_to_langfuse
from app.utils.file_security import validate_file_path, sanitize_filename

router = APIRouter(prefix="/dataset", tags=["Dataset Generation"])
logger = logging.getLogger(__name__)

# --- Schemas ---

class GenerateSimpleRequest(BaseModel):
    description: Optional[str] = None
    count: int = Field(5, le=100)
    is_random: bool = False

class GenerateSimpleResponse(BaseModel):
    items: List[Dict[str, str]] # Simple question/answer pairs
    count: int

class GenerateGTRequest(BaseModel):
    input_data: List[Dict[str, Any]] # e.g. list of existing Q&A dicts
    adversarial_level: float = Field(0.0, ge=0.0, le=1.0)

class GenerateGTResponse(BaseModel):
    items: List[EvalItem]
    count: int

class SaveDatasetRequest(BaseModel):
    name: str # Filename or dataset name
    items: List[EvalItem]
    as_ground_truth: bool = False

class SaveDatasetResponse(BaseModel):
    path: str
    item_count: int
    message: str

# --- Instantiation ---
generator_service = DatasetGenerator()
DATASETS_DIR = "datasets"

# --- Endpoints ---

@router.post("/generate/simple", response_model=GenerateSimpleResponse)
async def generate_simple(request: GenerateSimpleRequest):
    """
    Generate simple Q&A pairs (up to 100) from a description or randomly.
    """
    try:
        items = await generator_service.generate_simple_dataset(
            description=request.description,
            count=request.count,
            is_random=request.is_random
        )
        return GenerateSimpleResponse(items=items, count=len(items))
    except Exception as e:
        logger.error(f"Simple generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/ground-truth", response_model=GenerateGTResponse)
async def generate_ground_truth(request: GenerateGTRequest):
    """
    Generate a Ground Truth dataset (EvalItems) from existing data (list of Q&A dicts).
    'adversarial_level' (0.0 - 1.0) controls how tricky/different the questions are.
    """
    try:
        items = await generator_service.generate_ground_truth_from_data(
            input_data=request.input_data,
            adversarial_level=request.adversarial_level
        )
        return GenerateGTResponse(items=items, count=len(items))
    except Exception as e:
        logger.error(f"GT generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/ground-truth/from-file", response_model=GenerateGTResponse)
async def generate_ground_truth_from_file(
    file: UploadFile = File(...),
    adversarial_level: float = Form(0.0)
):
    """
    Generate Ground Truth dataset from an uploaded JSON file (List of Q&A).
    """
    try:
        content = await file.read()
        try:
            input_data = json.loads(content)
        except json.JSONDecodeError:
             raise HTTPException(status_code=400, detail="Invalid JSON file.")
        
        if not isinstance(input_data, list):
             raise HTTPException(status_code=400, detail="JSON must be a list of objects.")

        items = await generator_service.generate_ground_truth_from_data(
            input_data=input_data,
            adversarial_level=adversarial_level
        )
        return GenerateGTResponse(items=items, count=len(items))
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"GT file generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep existing save/sync endpoints

@router.post("/save", response_model=SaveDatasetResponse)
async def save_dataset(request: SaveDatasetRequest):
    """
    Save a list of EvalItems as a named dataset (JSON file).
    """
    try:
        if not os.path.exists(DATASETS_DIR):
            os.makedirs(DATASETS_DIR)

        # Sanitize and validate filename to prevent path traversal
        filename = request.name
        if not filename.endswith(".json"):
            filename += ".json"

        # Validate path stays within DATASETS_DIR
        try:
            path = validate_file_path(DATASETS_DIR, filename)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filename: {str(e)}"
            )
        
        data_dicts = [item.dict() for item in request.items]

        # Validate if ground truth
        if request.as_ground_truth:
             try:
                 validate_dataset(data_dicts) 
             except Exception as ve:
                 raise HTTPException(status_code=400, detail=f"Ground Truth validation failed: {ve}")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data_dicts, f, indent=2, ensure_ascii=False)
            
        return SaveDatasetResponse(
            path=path, 
            item_count=len(data_dicts), 
            message="Dataset saved successfully."
        )

    except Exception as e:
        logger.error(f"Save dataset failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-langfuse")
async def sync_langfuse(request: SaveDatasetRequest):
    """
    Sync provided items to a Langfuse dataset.
    """
    try:
        client = Langfuse()
        success = sync_dataset_to_langfuse(client, request.items, dataset_name=request.name)
        
        if not success:
             raise HTTPException(status_code=500, detail="Failed to sync to Langfuse")
             
        return {"status": "success", "message": f"Synced {len(request.items)} items to dataset '{request.name}'"}
    except Exception as e:
        logger.error(f"Langfuse sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_datasets():
    """List available datasets in the datasets directory."""
    if not os.path.exists(DATASETS_DIR):
        return {"datasets": []}
    
    files = [f for f in os.listdir(DATASETS_DIR) if f.endswith(".json")]
    return {"datasets": files}
