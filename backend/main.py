"""
Career Copilot RAG Backend - Main FastAPI Application
Implements the 7-step RAG architecture for career guidance and course recommendations.
Enhanced with: Conversation Memory, FAISS Semantic Search, Roles Knowledge Base.
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import API_HOST, API_PORT, LOG_LEVEL
from models import ChatRequest, ChatResponse, CourseDetail, ErrorDetail
from data_loader import data_loader
from llm.groq_client import get_llm_client
from memory import conversation_memory
from roles_kb import roles_kb
from pipeline import (
    IntentRouter,
    SemanticLayer,
    SkillExtractor,
    CourseRetriever,
    RelevanceGuard,
    ResponseBuilder,
    ConsistencyChecker,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global pipeline components (initialized on startup)
llm = None
intent_router = None
semantic_layer = None
skill_extractor = None
retriever = None
relevance_guard = None
response_builder = None
consistency_checker = None
semantic_search_enabled = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    global llm, intent_router, semantic_layer, skill_extractor
    global retriever, relevance_guard, response_builder, consistency_checker
    global semantic_search_enabled
    
    logger.info("Starting Career Copilot RAG Backend...")
    
    # Load data
    if not data_loader.load_all():
        logger.error("Failed to load data files")
        raise RuntimeError("Data loading failed")
    
    # Load roles knowledge base
    roles_kb.load()
    logger.info("Roles knowledge base loaded")
    
    # Try to load semantic search (optional)
    try:
        from semantic_search import semantic_search
        if semantic_search.load():
            semantic_search_enabled = True
            logger.info("FAISS semantic search enabled")
        else:
            logger.warning("FAISS semantic search not available, using skill-based only")
    except Exception as e:
        logger.warning(f"Semantic search disabled: {e}")
    
    # Initialize LLM
    try:
        llm = get_llm_client()
        logger.info("LLM client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        raise
    
    # Initialize pipeline components
    intent_router = IntentRouter(llm)
    semantic_layer = SemanticLayer(llm)
    skill_extractor = SkillExtractor()
    retriever = CourseRetriever()
    relevance_guard = RelevanceGuard()
    response_builder = ResponseBuilder(llm)
    consistency_checker = ConsistencyChecker()
    
    logger.info("All pipeline components initialized ✓")
    
    yield
    
    logger.info("Shutting down...")


app = FastAPI(
    title="Career Copilot RAG API",
    description="AI-powered career guidance and course recommendation system",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "career-copilot-rag",
        "version": "2.0.0",
        "data_loaded": data_loader.courses_df is not None,
        "semantic_search": semantic_search_enabled,
        "roles_loaded": len(roles_kb.roles) > 0,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint implementing the 7-step RAG pipeline.
    
    Steps:
    1. Intent Router - Classify user intent (with conversation context)
    2. Semantic Layer - Deep semantic understanding
    3. Skill Extractor - Extract and validate skills (+ role-based skills)
    4. Retriever - Fetch relevant courses (skill-based + semantic)
    5. Relevance Guard - Filter irrelevant results
    6. Response Builder - Generate dynamic response (with roadmap for career guidance)
    7. Consistency Check - Validate against data
    """
    request_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())
    
    logger.info(f"[{request_id}] Processing: {request.message[:50]}...")
    
    try:
        # Get conversation context
        context_str = conversation_memory.get_context(session_id)
        session_state = conversation_memory.get_session_state(session_id)
        conversation_memory.add_user_message(session_id, request.message)
        
        # Step 1: Intent Router (with context)
        intent_result = await intent_router.classify(request.message, context_str)
        logger.info(f"[{request_id}] Intent: {intent_result.intent.value}")
        
        # Step 2: Semantic Understanding
        semantic_result = await semantic_layer.analyze(request.message, intent_result)
        logger.info(f"[{request_id}] Skills extracted: {semantic_result.extracted_skills}")
        
        # Step 3: Skill Extraction & Validation
        skill_result = skill_extractor.validate_and_filter(semantic_result)
        
        # If role-based, get skills from roles KB
        if intent_result.role:
            # Try roles knowledge base first
            kb_skills = roles_kb.get_skills_for_role(intent_result.role)
            if kb_skills:
                existing = set(skill_result.validated_skills)
                for skill in kb_skills:
                    normalized = data_loader.validate_skill(skill)
                    if normalized and normalized not in existing:
                        skill_result.validated_skills.append(normalized)
            else:
                # Fallback to skill extractor suggestions
                role_skills = skill_extractor.suggest_skills_for_role(intent_result.role)
                existing = set(skill_result.validated_skills)
                for skill in role_skills:
                    if skill not in existing:
                        skill_result.validated_skills.append(skill)
        
        logger.info(f"[{request_id}] Validated skills: {skill_result.validated_skills}")
        
        # Step 4: Retrieval
        courses = retriever.retrieve(
            skill_result,
            level_filter=intent_result.level,
        )
        
        # If specific course query, search by title
        if intent_result.specific_course:
            courses = retriever.retrieve_by_title(intent_result.specific_course)
        
        # If CATALOG_BROWSING and no courses found, get sample of all courses
        if intent_result.intent.value == "CATALOG_BROWSING" and not courses:
            courses = retriever.browse_all(limit=30)
            logger.info(f"[{request_id}] Catalog browsing: showing {len(courses)} courses")
        
        # Enhance with semantic search if available and few results
        if semantic_search_enabled and len(courses) < 5 and intent_result.intent.value != "CATALOG_BROWSING":
            try:
                from semantic_search import semantic_search
                semantic_results = semantic_search.search(request.message, top_k=10)
                seen_ids = {c.course_id for c in courses}
                for course_id, score in semantic_results:
                    if course_id not in seen_ids:
                        course = retriever.get_course_details(course_id)
                        if course:
                            courses.append(course)
                            seen_ids.add(course_id)
            except Exception as e:
                logger.warning(f"Semantic search fallback failed: {e}")
        
        logger.info(f"[{request_id}] Retrieved {len(courses)} courses")
        
        # Step 5: Relevance Guard
        filtered_courses = relevance_guard.filter(
            courses,
            intent_result,
            skill_result,
            request.message,
        )
        
        # Step 6: Response Builder
        answer, projects, selected_courses = await response_builder.build(
            intent_result,
            filtered_courses,
            skill_result,
            request.message,
            context=session_state,
        )
        
        # Add roadmap for career guidance if available
        if intent_result.intent.value == "CAREER_GUIDANCE" and intent_result.role:
            roadmap = roles_kb.get_roadmap_for_role(intent_result.role)
            if roadmap:
                answer += f"\n\n### 📍 خطة التطور:\n{roadmap}"
        
        # Step 7: Consistency Check
        validated_answer, validated_courses = consistency_checker.final_check(
            answer,
            selected_courses,
        )
        
        # Limit courses for response (display limit)
        display_courses = relevance_guard.limit_results(validated_courses, max_courses=10)
        
        # Store assistant response in memory
        conversation_memory.add_assistant_message(
            session_id,
            validated_answer,
            intent=intent_result.intent.value,
            role=intent_result.role,
            skills=skill_result.validated_skills,
        )
        
        return ChatResponse(
            session_id=session_id,
            intent=intent_result.intent.value,
            answer=validated_answer,
            courses=display_courses,
            projects=projects,
            error=None,
            request_id=request_id,
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Pipeline error: {e}", exc_info=True)
        
        return ChatResponse(
            session_id=session_id,
            intent="ERROR",
            answer="عذراً، حدث خطأ أثناء معالجة طلبك. جرب تاني.",
            courses=[],
            projects=[],
            error=ErrorDetail(
                code="PIPELINE_ERROR",
                message=str(e),
            ),
            request_id=request_id,
        )


@app.get("/roles")
async def list_roles():
    """Get list of available roles from knowledge base."""
    return {
        "roles": roles_kb.get_all_roles(),
        "count": len(roles_kb.roles),
    }


@app.get("/categories")
async def list_categories():
    """Get list of available course categories."""
    return {
        "categories": data_loader.get_all_categories(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level=LOG_LEVEL.lower(),
    )
