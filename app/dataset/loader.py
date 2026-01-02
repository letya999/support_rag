import json
import os
from typing import List, Optional
from langfuse import Langfuse
from app.dataset.schema import EvalItem
from app.dataset.validator import validate_dataset

# Default to the datasets directory in the project root
DEFAULT_DATASET_NAME = "ground_truth_dataset.json"
DATASET_NAME = "ground-truth-retrieval-eval"

def load_ground_truth_dataset(file_path: Optional[str] = None) -> List[EvalItem]:
    """
    Load and validate ground truth dataset.
    If file_path is not provided, uses DEFAULT_DATASET_NAME from datasets/ directory.
    """
    if file_path is None:
        file_path = os.path.join("datasets", DEFAULT_DATASET_NAME)
        
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found at: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return validate_dataset(data)

def sync_dataset_to_langfuse(
    langfuse_client: Langfuse,
    dataset_items: List[EvalItem],
    dataset_name: str = DATASET_NAME
) -> bool:
    """Sync dataset to Langfuse."""
    if not langfuse_client:
        return False
        
    try:
        # Check existence
        try:
            langfuse_client.get_dataset(dataset_name)
            return True # Already exists, skipping for now
        except:
            pass # Does not exist
            
        langfuse_client.create_dataset(name=dataset_name)
        
        for item in dataset_items:
            langfuse_client.create_dataset_item(
                dataset_name=dataset_name,
                input={"question": item.question},
                expected_output={
                    "expected_chunks": item.expected_chunks,
                    "expected_answer": item.expected_answer,
                    "intent": item.expected_intent,
                    "category": item.expected_category,
                    "action": item.expected_action
                }
            )
        return True
    except Exception as e:
        print(f"Failed to sync dataset: {e}")
        return False
