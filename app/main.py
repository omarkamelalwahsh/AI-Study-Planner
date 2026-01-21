from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import chat, health
from app.core.errors import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.middleware.logging import RequestLoggingMiddleware

app = FastAPI(
    title="Career Copilot RAG",
    version="1.0.0",
    description="Production-grade RAG Chat System with Mixtral 8x7B via Ollama"
)

# Startup: Ensure DB Tables Exist
from app.db import engine, Base
# Import models to ensure they are registered with Base
from app.models import ChatSession, ChatMessage

@app.on_event("startup")
def on_startup():
    import logging
    # Setup simple file logger for debugging
    fhandler = logging.FileHandler("startup_debug.log", mode='w')
    fhandler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger = logging.getLogger("startup")
    logger.setLevel(logging.INFO)
    logger.addHandler(fhandler)
    
    logger.info("Startup event triggered.")
    logger.info(f"Engine URL: {engine.url}")
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Base.metadata.create_all executed successfully.")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")






# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # default vite port
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Logging Middleware
app.add_middleware(RequestLoggingMiddleware)

# Exception Handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# API Routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

@app.post("/debug-groq")
async def debug_groq():
    """
    Force a simple request to Groq to verify connectivity.
    """
    from app.llm.factory import get_llm
    try:
        llm = get_llm()
        messages = [{"role": "user", "content": "Reply with exactly this word: READY. Do not add anything else."}]
        
        full_resp = ""
        async for chunk in llm.stream(messages):
            full_resp += chunk
            
        return {"reply": full_resp}
    except Exception as e:
        return {"error": str(e)}


# Serve Frontend Static Files
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Check if build directory exists
FRONTEND_DIST = os.path.join(os.getcwd(), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # Mount assets (JS/CSS)
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    # Serve Index for Root and SPA Routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Allow API routes to pass through (already handled by routers above)
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("openapi.json"):
             # If it falls through here, it means 404 on API
             # But FastAPI router priority handles defined routes first.
             # This catch-all is only if no other route matched.
             raise StarletteHTTPException(status_code=404, detail="Not Found")

        # Serve index.html for everything else (SPA)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

else:
    @app.get("/")
    def root():
        return {
            "message": "Career Copilot RAG API (Frontend build not found)",
            "tip": "Run 'npm run build' in frontend directory to serve UI here."
        }
