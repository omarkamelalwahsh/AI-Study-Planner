"""
Error handlers for FastAPI application.

Provides consistent error responses across all endpoints.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions (4xx, 5xx errors).
    
    Args:
        request: The incoming request
        exc: The HTTP exception
        
    Returns:
        JSONResponse with error details
    """
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.method} {request.url.path}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": "HTTP_ERROR"
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (422 Unprocessable Entity).
    
    Args:
        request: The incoming request
        exc: The validation exception
        
    Returns:
        JSONResponse with validation error details
    """
    logger.warning(f"Validation error: {exc} - {request.method} {request.url.path}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "detail": str(exc.errors()),
            "code": "VALIDATION_ERROR"
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions (500 Internal Server Error).
    
    Args:
        request: The incoming request
        exc: The exception
        
    Returns:
        JSONResponse with error details
    """
    logger.error(f"Internal error: {exc} - {request.method} {request.url.path}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "code": "INTERNAL_ERROR"
        }
    )
