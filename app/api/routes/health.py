from fastapi import APIRouter
from pydantic import BaseModel
import os

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    version: str
    llm_provider: str
    llm_model: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for monitoring and diagnostics.
    
    Returns:
        HealthResponse: Service status and configuration info
    """
    return HealthResponse(
        status="ok",
        service="Career Copilot RAG",
        version="1.0.0",
        llm_provider=os.getenv("LLM_PROVIDER", "groq"),
        llm_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    )
