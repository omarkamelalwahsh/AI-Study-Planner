"""
Health check endpoint.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import HealthResponse, Course
from app.config import settings
from app.retrieval import _faiss_index
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    Returns status of: database, Groq API key, vector store, course count.
    """
    status = "ok"
    
    # Check database
    try:
        result = await db.execute(select(func.count()).select_from(Course))
        course_count = result.scalar() or 0
        database_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_status = "error"
        course_count = 0
        status = "degraded"
    
    # Check Groq API key
    groq_key_status = "configured" if settings.groq_api_key and settings.groq_api_key != "INSERT_YOUR_GROQ_API_KEY_HERE" else "missing"
    if groq_key_status == "missing":
        status = "degraded"
    
    # Check vector store
    vector_store_status = "loaded" if _faiss_index is not None else "not_loaded"
    if vector_store_status == "not_loaded":
        status = "degraded"
    
    return HealthResponse(
        status=status,
        database=database_status,
        groq_api_key=groq_key_status,
        vector_store=vector_store_status,
        course_count=course_count
    )
