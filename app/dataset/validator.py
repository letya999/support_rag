from typing import List
from pydantic import BaseModel, ValidationError
from app.dataset.schema import EvalItem

class EvalDataset(BaseModel):
    items: List[EvalItem]

def validate_dataset(data: List[dict]) -> List[EvalItem]:
    """
    Validate dataset items.
    """
    try:
        dataset = EvalDataset(items=data)
        return dataset.items
    except ValidationError as e:
        raise ValueError(f"Invalid dataset: {e}")
