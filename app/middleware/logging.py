"""
Request logging middleware for FastAPI.

Logs all incoming requests and outgoing responses with timing information.
"""
import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests and responses.
    
    Logs:
    - Request method and path
    - Response status code
    - Request duration
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and log details.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response from the handler
        """
        start_time = time.time()
        
        # Log incoming request
        logger.info(f"→ {request.method} {request.url.path}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"← {request.method} {request.url.path} "
            f"[{response.status_code}] {duration:.3f}s"
        )
        
        return response
