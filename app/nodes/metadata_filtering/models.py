from pydantic import BaseModel
from typing import Optional

class FilteringOutput(BaseModel):
    filter_used: bool
    fallback_triggered: bool
    filtering_reason: str
    category_filter: Optional[str] = None
