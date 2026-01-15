from pydantic import BaseModel
from typing import Optional

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    weeks: int = 4
    hours_per_week: float = 10.0

class PlanGenerateRequest(BaseModel):
    query_id: Optional[int] = None
    query_text: Optional[str] = None
    weeks: int
    hours_per_week: float
