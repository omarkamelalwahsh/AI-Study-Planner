from pydantic import BaseModel
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
