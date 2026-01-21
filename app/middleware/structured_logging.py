import time
import logging
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

logger = logging.getLogger("app.middleware")

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        
        # Log request start
        logger.info(f"Request started: {request.method} {request.url.path} (ID: {request_id})")
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(f"Request failed: {request.method} {request.url.path} (ID: {request_id})")
            raise e
            
        process_time = time.time() - start_time
        
        # Log request end with latency
        logger.info({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": f"{process_time * 1000:.2f}",
            "client": request.client.host if request.client else "unknown"
        })
        
        response.headers["X-Request-ID"] = request_id
        return response
