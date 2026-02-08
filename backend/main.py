"""
Career Copilot RAG Backend - Main FastAPI Application
Implements the 7-step RAG architecture for career guidance and course recommendations.
Enhanced with: Conversation Memory, FAISS Semantic Search, Roles Knowledge Base.
"""

import logging
import uuid
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import API_HOST, API_PORT, LOG_LEVEL
from models import (
    ChatRequest,
    ChatResponse,
    CourseDetail,
    ErrorDetail,
    IntentType,
    IntentResult,
    ChoiceQuestion,
    FlowStateUpdates,
    SemanticResult,
    SkillValidationResult,
    OneQuestion,
    NextAction,
)
from data_loader import data_loader
from llm.groq_gateway import get_llm_gateway
from memory import conversation_memory
from database.session_manager import session_manager
from roles_kb import roles_kb
from pipeline import (
    IntentRouter,
    SemanticLayer,
    SkillExtractor,
    CourseRetriever,
    RelevanceGuard,
    ResponseBuilder,
    ConsistencyChecker,
    FollowupResolver,
)
from pipeline.lost_user_flow import get_lost_user_v2_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Global pipeline components (initialized on startup)
llm = None
intent_router = None
semantic_layer = None
skill_extractor = None
relevance_guard = None
response_builder = None
consistency_checker = None
followup_resolver = None
semantic_search_enabled = False
semantic_search = None


def _is_arabic_text(text: str) -> bool:
    try:
        return data_loader.is_arabic(text)
    except Exception:
        # ultra-safe fallback
        return any("\u0600" <= ch <= "\u06FF" for ch in (text or ""))


def _safe_intent_value(intent) -> str:
    # intent might be Enum or str
    return intent.value if hasattr(intent, "value") else str(intent)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    global llm, intent_router, semantic_layer, skill_extractor
    global retriever, relevance_guard, response_builder, consistency_checker, followup_resolver
    global semantic_search_enabled, semantic_search

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
        from semantic_search import semantic_search as _semantic_search
        semantic_search = _semantic_search
        if semantic_search.load():
            semantic_search_enabled = True
            logger.info("FAISS semantic search enabled")
        else:
            logger.warning("FAISS semantic search not available, using skill-based only")
    except Exception as e:
        logger.warning(f"Semantic search disabled: {e}")

    # Initialize Database
    try:
        await session_manager.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # We might continue without DB if strictness allows, but let's log it.

    # Initialize LLM
    try:
        llm = get_llm_gateway()
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
    followup_resolver = FollowupResolver()

    logger.info("All pipeline components initialized ✓")

    # Startup validation
    if not hasattr(intent_router, "route"):
        raise RuntimeError("IntentRouter must have a 'route' method. Interface compatibility check failed.")
    if not hasattr(consistency_checker, "check"):
        raise RuntimeError("ConsistencyChecker must have a 'check' method. Interface compatibility check failed.")

    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Career Copilot RAG API",
    description="AI-powered career guidance and course recommendation system",
    version="2.0.0",
    lifespan=lifespan,
)

# --- GLOBAL EXCEPTION HANDLER ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Wraps all unhandled exceptions in ChatResponse format.
    IMPORTANT: must NEVER return invalid intent labels.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    is_ar = _is_arabic_text(getattr(request, "url", "").path or "")
    msg = "حدث خطأ غير متوقع. جرّب تاني بعد لحظات." if is_ar else "Unexpected error occurred. Please try again."

    return JSONResponse(
        status_code=500,
        content=ChatResponse(
            intent=IntentType.UNKNOWN,
            answer=msg,
            courses=[],
            categories=[],
            next_actions=[NextAction(text="إعادة المحاولة" if is_ar else "Try Again", type="retry")],
            session_state={},
            errors=[f"{type(exc).__name__}: {str(exc)}"],
            meta={"type": type(exc).__name__}
        ).model_dump()
    )


@app.get("/health")
async def health_check():
    """Requirement G: Production Health Check."""
    return {
        "status": "healthy",
        "service": "career-copilot-rag",
        "version": "2.0.0",
        "data_loaded": data_loader.courses_df is not None,
        "retriever": retriever is not None,
        "memory": conversation_memory is not None,
        "semantic_search": semantic_search_enabled,
        "roles_loaded": len(roles_kb.roles) > 0,
    }


@app.middleware("http")
async def debug_logging_middleware(request: Request, call_next):
    """Middleware to log every request with ID and timing."""
    req_id = str(uuid.uuid4())
    logger.info(f"⚡ [START] {request.method} {request.url.path} | ID: {req_id}")
    start_time = time.time()

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(f"✅ [DONE] {request.method} {request.url.path} | ID: {req_id} | Time: {process_time:.2f}ms | Status: {response.status_code}")
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"❌ [ERROR] {request.method} {request.url.path} | ID: {req_id} | Time: {process_time:.2f}ms | Exception: {e}")
        raise


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload-cv", response_model=ChatResponse, response_model_by_alias=True)
async def upload_cv(file: UploadFile = File(...), session_id: str = Form(None)):
    """
    Handle CV upload (PDF/DOCX/Image).
    Extracts text and triggers CV_ANALYSIS intent.
    """
    request_id = str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())
    logger.info(f"[{request_id}] Processing CV Upload: {file.filename}")

    try:
        content = await file.read()
        filename = (file.filename or "").lower()
        extracted_text = ""

        try:
            from services.file_service import FileService
            extracted_text = FileService.extract_text(content, filename)
        except Exception as e:
            logger.error(f"FileService failed: {e}")
            extracted_text = ""

        await conversation_memory.add_user_message(session_id, f"[Uploaded CV: {file.filename}]")

        session_state = await conversation_memory.get_session_state(session_id)
        session_state["last_intent"] = IntentType.CAREER_GUIDANCE

        user_message = f"Analyze this CV content: {extracted_text[:4000]}"

        # Map CV analysis to CAREER_GUIDANCE for unified tracking
        intent_result = IntentResult(intent=IntentType.CAREER_GUIDANCE, topic="CV Analysis")

        try:
            semantic_result = await semantic_layer.analyze(user_message, intent_result)
        except Exception as sem_err:
            logger.error(f"Semantic analysis failed on CV: {sem_err}")
            semantic_result = SemanticResult(primary_domain="General", brief_explanation="Could not analyze CV deeply.", is_in_catalog=True)

        skill_result = skill_extractor.validate_and_filter(semantic_result)

        cv_profile = {
            "raw_text": extracted_text[:4000],
            "skills": skill_result.validated_skills,
            "roles": semantic_result.secondary_domains,
            "experience_level": semantic_result.user_level
        }
        session_state["cv_profile"] = cv_profile
        await conversation_memory.update_session_state(session_id, session_state)

        # Retrieve courses based on extracted skills
        courses = retriever.retrieve(skill_result)[:6]

        chat_res = await response_builder.build(
            intent_result,
            courses,
            skill_result,
            user_message,
            context=session_state
        )

        chat_res.session_id = session_id
        chat_res.request_id = request_id
        chat_res.meta = {"flow": "cv_upload_v2"}

        await conversation_memory.add_assistant_message(
            session_id,
            chat_res.answer,
            intent=IntentType.CAREER_GUIDANCE,
            skills=skill_result.validated_skills
        )

        return chat_res

    except Exception as e:
        logger.error(f"CV Upload Error: {e}", exc_info=True)
        return ChatResponse(
            intent=IntentType.UNKNOWN,
            answer="حصلت مشكلة أثناء رفع الملف. جرّب PDF أو DOCX، أو ابعتلي هدفك الوظيفي وأنا أساعدك فورًا.",
            courses=[],
            categories=[],
            next_actions=[NextAction(text="إعادة المحاولة" if _is_arabic_text(file.filename) else "Try Again", type="retry")],
            session_state={},
            errors=[str(e)],
            request_id=request_id,
            meta={"flow": "cv_upload_error"}
        )


# --- UNIFIED SEARCH PIPELINE ---
async def run_course_search_pipeline(
    intent_result: IntentResult,
    semantic_result: SemanticResult,
    request_id: str,
    session_state: dict,
    is_more_request: bool,
    user_message: str
) -> tuple[SkillValidationResult, list[CourseDetail]]:
    """
    Executes the standard Course Search Pipeline:
    Skill Extraction -> Retrieval (with Fallbacks) -> Relevance Guard.
    """
    logger.info(f"[{request_id}] COURSE_SEARCH pipeline executed")

    # Step 3: Skill & Role Extraction
    skill_result = skill_extractor.validate_and_filter(semantic_result)

    # --- SEED SKILL INJECTION ---
    if not skill_result.validated_skills and getattr(intent_result, "primary_domain", None) == "Backend Development":
        backend_seeds = ["sql", "databases", "api", "php", "web development", "javascript"]
        for s in backend_seeds:
            norm = data_loader.validate_skill(s)
            if norm and norm not in skill_result.validated_skills:
                skill_result.validated_skills.append(norm)

    # Role-based skill completion
    if intent_result.role:
        kb_skills = roles_kb.get_skills_for_role(intent_result.role)
        if kb_skills:
            existing = set(skill_result.validated_skills)
            for skill in kb_skills:
                normalized = data_loader.validate_skill(skill)
                if normalized and normalized not in existing:
                    skill_result.validated_skills.append(normalized)

    if skill_result.validated_skills:
        logger.info(f"[{request_id}] Validated skills: {skill_result.validated_skills}")

    # Step 4: Retrieval

    # --- RULE 4A: SQL/Database Topic Expansion ---
    db_keywords = ["sql", "database", "databases", "mysql", "postgres", "postgresql", "db", "قواعد بيانات", "داتابيز", "my sql", "بوستجريس"]
    expanded_courses = []
    if intent_result.topic and any(kw in intent_result.topic.lower() for kw in db_keywords):
        logger.info(f"[{request_id}] RULE 4A Triggered: Forcing Database track expansion.")
        sql_results = retriever.retrieve_by_title("SQL")
        db_results = retriever.retrieve_by_title("Database")
        sec_results = retriever.browse_by_category("Data Security")
        seen_ids = set()
        for c in sql_results[:5] + db_results[:5] + sec_results[:2]:
            if c and c.course_id not in seen_ids:
                expanded_courses.append(c)
                seen_ids.add(c.course_id)

    # --- RULE 4B: Sales Manager Hybrid Retrieval ---
    manager_keywords = ["مدير", "إدارة", "قيادة", "ليدر", "lead", "manager", "leadership"]
    sales_keywords = ["sales", "مبيعات", "بيع", "selling"]
    msg_lower = (user_message or "").lower()
    is_manager = any(kw in msg_lower for kw in manager_keywords)
    is_sales = any(kw in msg_lower for kw in sales_keywords)

    hybrid_courses = []
    if is_manager and is_sales:
        logger.info(f"[{request_id}] RULE 4B Triggered: Hybrid Sales + Management retrieval.")
        sales_results = retriever.browse_by_category("Sales")
        mgmt_results = retriever.browse_by_category("Leadership & Management")
        biz_results = retriever.browse_by_category("Business Fundamentals")
        seen_ids = set()
        for c in sales_results[:4] + mgmt_results[:4] + biz_results[:2]:
            if c and c.course_id not in seen_ids:
                hybrid_courses.append(c)
                seen_ids.add(c.course_id)

    # 4.1 Skill-based
    raw_courses = retriever.retrieve(
        skill_result,
        level_filter=intent_result.level,
        focus_area=semantic_result.focus_area,
        tool=semantic_result.tool,
    )

    # Merge specialized results
    specialized = hybrid_courses or expanded_courses
    if specialized:
        spec_ids = {s.course_id for s in specialized}
        raw_courses = specialized + [c for c in raw_courses if c.course_id not in spec_ids]

    # 4.2 Fallbacks (Topic/Title)
    # IMPORTANT: remove invalid enum name CATALOG_BROWSING -> use CATALOG_BROWSE
    course_needing_intents = [
        IntentType.COURSE_SEARCH,
        IntentType.CATALOG_BROWSE,
        IntentType.FOLLOW_UP,
        IntentType.CAREER_GUIDANCE
    ]

    browsing_keywords = ["كورسات", "عاوز", "وريني", "courses", "show", "browse"]
    is_browsing = any(kw in msg_lower for kw in browsing_keywords)

    needs_fallback = (not raw_courses) and (intent_result.intent in course_needing_intents or is_browsing)

    if needs_fallback:
        TOPIC_MAP = {
            "برمجة": "Programming",
            "programming": "Programming",
            "تسويق": "Marketing",
            "marketing": "Marketing",
            "مبيعات": "Sales",
            "sales": "Sales",
            "تصميم": "Design",
            "design": "Design",
            "قيادة": "Leadership",
            "leadership": "Leadership",
            "موارد بشرية": "Human Resources",
            "hr": "Human Resources",
            "بايثون": "Python",
            "python": "Python",
            "فرونت": "Web Development",
            "frontend": "Web Development",
            "back": "Programming",
            "backend": "Programming",
            "data": "Data Science",
            "داتا": "Data Science",
        }

        fallback_topic = None
        for key, topic in TOPIC_MAP.items():
            if key in msg_lower:
                fallback_topic = topic
                break

        if not fallback_topic:
            fallback_topic = intent_result.specific_course or intent_result.slots.get("topic") or semantic_result.primary_domain

        if not fallback_topic and intent_result.intent == IntentType.FOLLOW_UP:
            fallback_topic = session_state.get("last_topic") or session_state.get("last_query")
            if fallback_topic:
                logger.info(f"[{request_id}] Follow-up Context Reuse: '{fallback_topic}'")

        if fallback_topic:
            logger.info(f"[{request_id}] Topic Fallback: '{fallback_topic}'")
            raw_courses = retriever.retrieve_by_title(fallback_topic)

        if not raw_courses:
            logger.info(f"[{request_id}] Direct title search: '{user_message}'")
            raw_courses = retriever.retrieve_by_title(user_message)

    logger.info(f"[{request_id}] Retrieved {len(raw_courses)} raw courses")

    # Step 5: Relevance Guard
    prev_domains = set(session_state.get("last_skills", []) + ([session_state.get("last_role")] if session_state.get("last_role") else []))

    filtered_courses = relevance_guard.filter(
        raw_courses,
        intent_result,
        skill_result,
        user_message,
        previous_domains=prev_domains,
        semantic_result=semantic_result
    )

    # FAIL-SAFE: If retrieval found courses but relevance guard filtered everything out
    if raw_courses and not filtered_courses:
        logger.warning(f"[{request_id}] FAIL-SAFE TRIGGERED: Populating empty response with Top 3 retrieved courses.")
        seen_ids = set()
        fail_safe_courses = []
        for course in raw_courses[:10]:
            if course.course_id not in seen_ids:
                fail_safe_courses.append(course)
                seen_ids.add(course.course_id)
                if len(fail_safe_courses) >= 3:
                    break
        filtered_courses = fail_safe_courses

    return skill_result, filtered_courses


@app.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def chat(request: ChatRequest):
    """Main chat endpoint implementing the consolidated RAG pipeline."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    
    # 1. Persistence & Context Loading
    await conversation_memory.add_user_message(session_id, request.message)
    session_state = await conversation_memory.get_session_state(session_id)

    # 1.1 HARD SCOPE OVERRIDE (Production Safety)
    # Ensure tech tracks are NEVER out-of-scope
    ALLOWED_TECH_KEYWORDS = {
        "software", "programming", "برمج", "data", "ai", "ذكاء", "cyber", "security", "سيبير", "it", 
        "product", "project", "منتج", "مشروع", "marketing", "تسويق", "ux", "ui", "design", "تصميم"
    }
    msg_lower = request.message.lower()
    force_in_scope = any(k in msg_lower for k in ALLOWED_TECH_KEYWORDS)
    if force_in_scope:
        logger.info(f"[{request_id}] Hard Scope Override: Tech keyword detected. Preventing OUT_OF_SCOPE.")

    # 1.5 SPECIAL: Lost User Multi-turn Flow (V2)
    # If we are already in the middle of a lost user flow, bypass intent detection
    if session_state.get("active_flow") == "lost_user_v2":
        logger.info(f"[{request_id}] Ongoing LOST_USER_FLOW_V2 detected")
        chat_res = get_lost_user_v2_response(session_id, session_state, request.message)
        
        # Sync session state
        await conversation_memory.update_session_state(session_id, chat_res.session_state)
        
        chat_res.request_id = request_id
        await conversation_memory.add_assistant_message(
            session_id, 
            chat_res.answer, 
            intent=chat_res.intent,
            state_updates=chat_res.session_state
        )
        return chat_res

    try:
        # 2. Intent Routing & Follow-up Resolution
        # Check explanation keywords (Static/Fast)
        intent_result = intent_router.check_explanation_keywords(request.message)
        
        # Check Follow-up / Pagination / State-based
        if not intent_result:
            intent_result = followup_resolver.resolve(request.message, session_state)
            
        # LLM Router (Fallback)
        if not intent_result:
            try:
                intent_result = await intent_router.route(request.message, session_state)
            except Exception as e:
                logger.error(f"Intent Router Failed: {e}")
                intent_result = IntentResult(intent=IntentType.UNKNOWN)

        logger.info(f"[{request_id}] Resolved Intent: {intent_result.intent}")

        # 2.5 SPECIAL: Lost User Fast-Path Trigger
        # If router flagged needs_one_question AND it's a general topic, it's likely a lost user
        if intent_result.intent == IntentType.CAREER_GUIDANCE and intent_result.needs_one_question and intent_result.topic == "General":
            logger.info(f"[{request_id}] Triggering LOST_USER_FLOW_V2 (Turn 1)")
            chat_res = get_lost_user_v2_response(session_id, session_state) # First turn doesn't need user_msg
            
            # Sync session state
            await conversation_memory.update_session_state(session_id, chat_res.session_state)
            
            chat_res.request_id = request_id
            await conversation_memory.add_assistant_message(
                session_id, 
                chat_res.answer, 
                intent=chat_res.intent,
                state_updates=chat_res.session_state
            )
            return chat_res

        # 3. Deterministic Fast-Paths (Browse / Out of Scope)
        if intent_result.intent == IntentType.CATALOG_BROWSE:
            all_cats = data_loader.get_all_categories()[:20]
            is_ar = _is_arabic_text(request.message)
            return ChatResponse(
                intent=IntentType.CATALOG_BROWSE,
                answer="دي أهم الأقسام اللي عندنا. اختار قسم وانا أطلعلك أفضل كورسات." if is_ar else "Here are our main catalog categories.",
                categories=all_cats,
                next_actions=[NextAction(text="استكشاف كل المجالات" if is_ar else "Explore All Domains", type="catalog_browse")],
                session_state=session_state,
                request_id=request_id
            )
            
        if intent_result.intent == IntentType.OUT_OF_SCOPE and not force_in_scope:
            # Step 5: Response Building (Strict out of scope answer)
            chat_res = await response_builder.build(
                intent_result=intent_result,
                courses=[],
                skill_result=SkillValidationResult(validated_skills=[]),
                user_message=request.message,
                context=session_state,
                semantic_result=SemanticResult(primary_domain="Out of Scope", is_in_catalog=False)
            )
            chat_res.session_id = session_id
            chat_res.request_id = request_id
            return chat_res
        elif intent_result.intent == IntentType.OUT_OF_SCOPE and force_in_scope:
            # Re-route to Career Guidance if it was falsely flagged as out of scope
            logger.info(f"[{request_id}] Rerouting false OUT_OF_SCOPE to CAREER_GUIDANCE")
            intent_result.intent = IntentType.CAREER_GUIDANCE
            intent_result.topic = "General"
            intent_result.needs_one_question = True


        # 4. Pipeline Execution (Search / Guidance)
        if intent_result.slots.get("is_pagination"):
            # Skip retrieval, use pre-retrieved IDs
            pre_ids = intent_result.slots.get("pre_retrieved_ids", [])
            filtered_courses = [retriever.get_course_details(cid) for cid in pre_ids if retriever.get_course_details(cid)]
            skill_result = SkillValidationResult(validated_skills=session_state.get("last_skills", []))
            semantic_result = SemanticResult(primary_domain="General", is_in_catalog=True)
        else:
            # Standard Pipeline
            # Step 2: Semantic Analysis
            previous_topic = session_state.get("last_topic")
            semantic_result = await semantic_layer.analyze(request.message, intent_result, previous_topic=previous_topic)
            
            # Step 3/4: Retrieval
            # RULE: Only run retrieval if intent is COURSE_SEARCH or needs_courses is explicitly True
            # For PROJECT_IDEAS, we skip retrieval completely as it relies on LLM generation.
            if intent_result.intent == IntentType.PROJECT_IDEAS:
                logger.info(f"[{request_id}] PROJECT_IDEAS: Skipping retrieval pipeline.")
                skill_result = skill_extractor.validate_and_filter(semantic_result)
                filtered_courses = []
            elif intent_result.intent == IntentType.COURSE_SEARCH or intent_result.needs_courses:
                skill_result, filtered_courses = await run_course_search_pipeline(
                    intent_result, semantic_result, request_id, session_state, False, request.message
                )
            else:
                logger.info(f"[{request_id}] Skipping retrieval: intent {intent_result.intent} does not need courses.")
                skill_result = skill_extractor.validate_and_filter(semantic_result)
                filtered_courses = []

        # 5. Response Building
        chat_res = await response_builder.build(
            intent_result=intent_result,
            courses=filtered_courses,
            skill_result=skill_result,
            user_message=request.message,
            context=session_state,
            semantic_result=semantic_result
        )

        # 6. Post-processing & Persistence
        chat_res.session_id = session_id
        chat_res.request_id = request_id
        chat_res.meta.update({"latency_ms": round((time.time() - start_time) * 1000, 2)})

        # Update Session State (Ensuring topic persistence)
        new_topic = intent_result.topic or (semantic_result.primary_domain if semantic_result else None) or session_state.get("last_topic")
        
        session_state.update({
            "last_topic": new_topic,
            "last_intent": _safe_intent_value(chat_res.intent),
            "last_skills": skill_result.validated_skills if skill_result else [],
            "all_relevant_course_ids": [c.course_id for c in filtered_courses] if filtered_courses else session_state.get("all_relevant_course_ids", [])
        })
        await conversation_memory.update_session_state(session_id, session_state)

        # Log AI response
        await conversation_memory.add_assistant_message(
            session_id, 
            chat_res.answer, 
            intent=chat_res.intent,
            state_updates=session_state # Future-proofing
        )

        return chat_res

    except Exception as e:
        logger.error(f"[{request_id}] Pipeline Failure: {e}", exc_info=True)
        is_ar = _is_arabic_text(request.message)
        return ChatResponse(
            intent=IntentType.UNKNOWN,
            answer="عذراً، حصلت مشكلة بسيطة. ممكن تجرّب تاني؟" if is_ar else "Sorry, there was a small issue. Please try again.",
            errors=[str(e)],
            next_actions=[NextAction(text="إعادة المحاولة" if is_ar else "Try Again", type="retry")],
            session_state=session_state,
            request_id=request_id
        )


@app.get("/courses/{course_id}", response_model=CourseDetail)
def get_course_details(course_id: str):
    """Fetch full details for a specific course by ID."""
    c = data_loader.get_course_by_id(course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")

    return CourseDetail(
        course_id=str(c.get("course_id", "")),
        title=c.get("title", ""),
        category=c.get("category"),
        level=c.get("level"),
        instructor=c.get("instructor"),
        duration_hours=c.get("duration_hours"),
        description_short=c.get("description_short"),
        description_full=c.get("description_full") or c.get("description"),
        cover=c.get("cover"),
    )

# Run with: uvicorn main:app --reload
