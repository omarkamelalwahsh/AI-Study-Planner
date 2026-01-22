"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.retrieval import load_vector_store
from app.routes import chat, health, courses, sessions
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info(f"Starting Career Copilot RAG API (env: {settings.app_env})")
    
    # Production validation: Fail fast if Groq API key missing
    if settings.is_production:
        if not settings.groq_api_key or settings.groq_api_key == "INSERT_YOUR_GROQ_API_KEY_HERE":
            logger.critical("CRITICAL: GROQ_API_KEY not configured in production!")
            raise RuntimeError(
                "Production startup failed: GROQ_API_KEY is missing or placeholder. "
                "Set a valid Groq API key in .env before starting in production mode."
            )
        logger.info("✓ Groq API key configured")
    
    # Load vector store
    logger.info("Loading vector store...")
    load_vector_store()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Career Copilot RAG API")


# Create FastAPI app
app = FastAPI(
    title="Career Copilot RAG API",
    description="Production RAG-first API for career course recommendations",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,  # Disable docs in prod
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS configuration
if settings.is_production:
    # Strict CORS in production
    allowed_origins = [settings.vite_api_base_url]
else:
    # Permissive CORS in development
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(chat.router, tags=["Chat"])
app.include_router(health.router, tags=["Health"])
app.include_router(courses.router, prefix="/courses", tags=["Courses"])
app.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Career Copilot RAG API",
        "version": "1.0.0",
        "environment": settings.app_env,
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development
    )
