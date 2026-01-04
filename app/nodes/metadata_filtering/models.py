from pydantic import BaseModel
from typing import Optional, List, Union

class FilteringOutput(BaseModel):
    filter_used: bool
    fallback_triggered: bool
    filtering_reason: str
    category_filter: Optional[Union[str, List[str]]] = None
