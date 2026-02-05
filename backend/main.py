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
from models import ChatRequest, ChatResponse, CourseDetail, ErrorDetail, IntentType, IntentResult, ChoiceQuestion, FlowStateUpdates
from data_loader import data_loader
from llm.groq_gateway import get_llm_gateway
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
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
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
semantic_search = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    global llm, intent_router, semantic_layer, skill_extractor
    global retriever, relevance_guard, response_builder, consistency_checker
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
    
    logger.info("All pipeline components initialized ✓")
    
    # Startup validation: Ensure components have correct methods
    if not hasattr(intent_router, 'route'):
        raise RuntimeError("IntentRouter must have a 'route' method. Interface compatibility check failed.")
    if not hasattr(consistency_checker, 'check'):
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
    """Wraps all unhandled exceptions in StandardResponse format."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=StandardResponse(
            intent="ERROR",
            message="حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.",
            courses=[],
            meta={"error": str(exc), "type": type(exc).__name__}
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
    """
    Middleware to log every request with ID and timing.
    """
    # Generate a request ID for tracing
    req_id = str(uuid.uuid4())
    
    # Log Start
    logger.info(f"⚡ [START] {request.method} {request.url.path} | ID: {req_id}")
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        # Log Success
        logger.info(f"✅ [DONE] {request.method} {request.url.path} | ID: {req_id} | Time: {process_time:.2f}ms | Status: {response.status_code}")
        return response
        
    except Exception as e:
        # Log Error
        process_time = (time.time() - start_time) * 1000
        logger.error(f"❌ [ERROR] {request.method} {request.url.path} | ID: {req_id} | Time: {process_time:.2f}ms | Exception: {e}")
        raise

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload-cv", response_model=ChatResponse)
async def upload_cv(
    file: UploadFile = File(...),
    session_id: str = Form(None)
):
    """
    Handle CV upload (PDF/DOCX/Image).
    Extracts text and triggers CV_UPLOAD intent.
    """
    request_id = str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())
    logger.info(f"[{request_id}] Processing CV Upload: {file.filename}")

    try:
        content = await file.read()
        filename = file.filename.lower()
        extracted_text = ""

        # Use dedicated FileService for parsing
        try:
             from services.file_service import FileService
             extracted_text = FileService.extract_text(content, filename)
        except Exception as e:
             logger.error(f"FileService failed: {e}")
             extracted_text = "Error processing file."

        # Simulate a Chat Request with the extracted text, forcing CV_UPLOAD intent handling
        conversation_memory.add_user_message(session_id, f"[Uploaded CV: {file.filename}]")
        
        session_state = conversation_memory.get_session_state(session_id)
        session_state["last_intent"] = IntentType.CV_ANALYSIS
        
        # Analyze first 4000 chars
        user_message = f"Analyze this CV content: {extracted_text[:4000]}"
        
        # 1. Intent Result (Forced)
        intent_result = IntentResult(intent=IntentType.CV_ANALYSIS)
        
        # 2. Semantic Analysis
        # Ensure we catch errors here too
        try:
            semantic_result = await semantic_layer.analyze(user_message, intent_result)
        except Exception as sem_err:
            logger.error(f"Semantic analysis failed on CV: {sem_err}")
            # Fallback semantic result
            from models import SemanticResult
            semantic_result = SemanticResult(primary_domain="General", brief_explanation="Could not analyze CV deeply.")
        
        # 3. Validated Skills
        skill_result = skill_extractor.validate_and_filter(semantic_result)
        
        # Store CV Profile in Session (Critical for "My CV" questions)
        cv_profile = {
            "raw_text": extracted_text[:4000],
            "skills": skill_result.validated_skills,
            "roles": semantic_result.secondary_domains, # Heuristic
            "experience_level": semantic_result.user_level
        }
        session_state["cv_profile"] = cv_profile
        conversation_memory.update_session_state(session_id, session_state)
        
        # 4. Filter Courses (If appropriate, mostly for "What fits my CV")
        # For Upload, we usually just give analysis.
        courses = [] 
        
        # 5. Response Builder
        answer, projects, selected_courses, skill_groups, learning_plan, dashboard, all_relevant, catalog_browsing, mode, f_question, refined_intent, _ = await response_builder.build(
            intent_result,
            courses,
            skill_result,
            user_message,
            context=session_state
        )
        
        # Store response
        conversation_memory.add_assistant_message(
            session_id,
            answer,
            intent=IntentType.CV_ANALYSIS,
            skills=skill_result.validated_skills
        )

        return ChatResponse(
            session_id=session_id,
            intent=IntentType.CV_ANALYSIS,
            answer=answer,
            courses=selected_courses,
            all_relevant_courses=all_relevant,
            projects=projects,
            skill_groups=skill_groups,
            catalog_browsing=catalog_browsing,
            learning_plan=learning_plan,
            dashboard=dashboard,
            error=None,
            request_id=request_id,
            ask=f_question if isinstance(f_question, ChoiceQuestion) else None,
            followup_question=f_question if isinstance(f_question, str) else None
        )

    except Exception as e:
        logger.error(f"CV Upload Error: {e}", exc_info=True)
        return ChatResponse(
             session_id=session_id,
             intent=IntentType.CV_ANALYSIS,
             answer="تمام، بس ملف السيرة الذاتية محتاج يتراجع تاني. ممكن تحاول ترفعه بصيغة تانية أو تسألني في أي مجال تحب تبدأ فيه؟" if data_loader.is_arabic(request.message) else "Got it, but the CV file might need a quick check. Could you try uploading it in a different format, or just tell me which field you're interested in?",
             courses=[],
             request_id=request_id,
             error=ErrorDetail(message=str(e), code="CV_PROCESSING_ERROR")
        )


from models import SemanticResult, SkillValidationResult

# --- UNIFIED SEARCH PIPELINE (Requirement: Single Entry Point) ---
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
    if not skill_result.validated_skills and intent_result.primary_domain == "Backend Development":
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
        # Ensure categories like Data Security are checked if relevant
        sec_results = retriever.browse_by_category("Data Security")
        seen_ids = set()
        for c in sql_results[:5] + db_results[:5] + sec_results[:2]:
            if c.course_id not in seen_ids:
                expanded_courses.append(c)
                seen_ids.add(c.course_id)

    # --- RULE 4B: Sales Manager Hybrid Retrieval ---
    manager_keywords = ["مدير", "إدارة", "قيادة", "ليدر", "lead", "manager", "leadership"]
    sales_keywords = ["sales", "مبيعات", "بيع", "selling"]
    msg_lower = user_message.lower()
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
            if c.course_id not in seen_ids:
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
        # Prioritize specialized results
        raw_courses = specialized + [c for c in raw_courses if c.course_id not in [s.course_id for s in specialized]]
    
    # 4.2 Fallbacks (Topic/Title)
    # Apply fallbacks for any intent that needs courses (not just COURSE_SEARCH)
    course_needing_intents = [IntentType.COURSE_SEARCH, IntentType.CATALOG_BROWSING, IntentType.FOLLOW_UP, 
                               IntentType.CAREER_GUIDANCE, IntentType.LEARNING_PATH]
    
    # Check if this is a browsing query (Arabic or English keywords)
    browsing_keywords = ["كورسات", "عاوز", "وريني", "courses", "show", "browse"]
    is_browsing = any(kw in user_message.lower() for kw in browsing_keywords)
    
    needs_fallback = (not raw_courses) and (intent_result.intent in course_needing_intents or is_browsing)
    
    if needs_fallback:
        # Arabic/English topic mapping + Broad keywords
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
            "baak": "Programming",
            "back": "Programming",
            "backend": "Programming",
            "data": "Data Science",
            "داتا": "Data Science",
        }
        msg_lower = user_message.lower()
        fallback_topic = None
        
        # Check map
        for key, topic in TOPIC_MAP.items():
             if key in msg_lower:
                 fallback_topic = topic
                 break
        
        # Check resolved topic from intent/semantic
        if not fallback_topic:
             fallback_topic = intent_result.specific_course or intent_result.slots.get("topic") or semantic_result.primary_domain
        
        # FOLLOW_UP Persistence: If no topic found, reuse last topic/query from session
        if not fallback_topic and intent_result.intent == IntentType.FOLLOW_UP:
             fallback_topic = session_state.get("last_topic") or session_state.get("last_query")
             if fallback_topic:
                 logger.info(f"[{request_id}] Follow-up Context Reuse: '{fallback_topic}'")

        if fallback_topic:
            logger.info(f"[{request_id}] Topic Fallback: '{fallback_topic}'")
            raw_courses = retriever.retrieve_by_title(fallback_topic)
        
        # If still empty, try raw message as title search
        if not raw_courses:
            logger.info(f"[{request_id}] Direct title search: '{user_message}'")
            raw_courses = retriever.retrieve_by_title(user_message)

    # V18 Fix: If this is a follow-up and we STILL have no courses and no context,
    # we should return a message asking for clarification, handled by response_builder later.
    
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
    
    # FAIL-SAFE: If retrieval found courses but relevance guard filtered everything out,
    # return top 3 from raw results to prevent zero-result failures
    if raw_courses and not filtered_courses:
        logger.warning(f"[{request_id}] FAIL-SAFE TRIGGERED: Populating empty response with Top 3 retrieved courses.")
        # Dedup and take top 3
        seen_ids = set()
        fail_safe_courses = []
        for course in raw_courses[:10]:  # Check first 10 for dedup
            if course.course_id not in seen_ids:
                fail_safe_courses.append(course)
                seen_ids.add(course.course_id)
                if len(fail_safe_courses) >= 3:
                    break
        filtered_courses = fail_safe_courses
    
    return skill_result, filtered_courses


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
    start_time = time.time()
    
    # Initialize session
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"[{request_id}] Processing CHAT request | Session: {session_id} | Msg: {request.message[:50]}...")
    
    # Add user message to memory
    conversation_memory.add_user_message(session_id, request.message)
    session_state = conversation_memory.get_session_state(session_id)
    
    # Setup for semantic result override (for testing or fast-paths)
    semantic_result_override = None

    try:
        # Step 1: Intent Router (Rock-Solid Interface)
        intent_result = await intent_router.route(request.message, session_state)
        
        # --- ZEDNY PRODUCTION RULES (Locking & Fallback) ---
        exploration_state = session_state.get("exploration", {})
        active_f = session_state.get("active_flow")
        stage = (exploration_state or {}).get("stage")
        
        if stage == "locked":
            chosen_domain = exploration_state.get("chosen_domain")
            msg = request.message.lower()
            if any(kw in msg for kw in ["خطة", "plan", "roadmap", "مسار"]):
                logger.info(f"[{request_id}] Rule 1 Trigger: Force LEARNING_PATH for {chosen_domain}")
                intent_result.intent = IntentType.LEARNING_PATH
                intent_result.topic = chosen_domain
                intent_result.confidence = 1.0
            elif any(kw in msg for kw in ["more", "كورسات", "كمان", "تانية"]):
                logger.info(f"[{request_id}] Rule 1 Trigger: Force COURSE_SEARCH for {chosen_domain}")
                intent_result.intent = IntentType.COURSE_SEARCH
                intent_result.topic = chosen_domain
                intent_result.confidence = 1.0
                intent_result.needs_courses = True
            else:
                logger.info(f"[{request_id}] Rule 1 Trigger: Force CAREER_GUIDANCE for {chosen_domain}")
                intent_result.intent = IntentType.CAREER_GUIDANCE
                intent_result.topic = chosen_domain
                intent_result.confidence = 1.0
        
        elif active_f == "EXPLORATION_FLOW":
             # Unified Prompt v1 Flow: Exploration transitions to COURSE_SEARCH
             # For intermediate steps, we keep it as EXPLORATION
             intent_result.intent = IntentType.EXPLORATION_FOLLOWUP
        
        else:
            undecided_triggers = ["مش عارف", "تايه", "محتار", "ساعدني", "مش عارف اختار", "I don't know", "help me choose"]
            if any(kw in request.message for kw in undecided_triggers):
                logger.info(f"[{request_id}] Rule 3 Trigger: Force EXPLORATION")
                intent_result.intent = IntentType.EXPLORATION
            
        logger.info(f"[{request_id}] Final Intent: {intent_result.intent.value if hasattr(intent_result.intent, 'value') else intent_result.intent}")
        
        # Check for ambiguous intent -> Catalog Browsing Fast Path
        if intent_result.intent == IntentType.CATALOG_BROWSING:
            logger.info(f"[{request_id}] Fast Path: Catalog Browsing/Ambiguous")
            
            # Use categories from intent result or fallback
            cats = intent_result.slots.get("categories", [])
            if not cats:
                 cats = ["Programming", "Data Science", "Marketing", "Business", "Design"]
            
            # We skip pipeline for pure browsing
            answer = "أهلاً بيك! أنا كارير كوبايلوت. أقدر أساعدك تلاقي كورسات، أرشحلك وظايف، أو أعملك خطة مذاكرة. تحب تبدأ بأي مجال؟"
            state_updates = {
                "last_intent": IntentType.CATALOG_BROWSING, 
                "last_role": None,
                "last_skills": [],
                "offered_categories": cats  # V17: Store offered categories for disambiguation resolution
            }
            conversation_memory.add_assistant_message(session_id, answer, intent=IntentType.CATALOG_BROWSING.value, state_updates=state_updates)
            
            from models import CatalogBrowsingData, CategoryDetail
            cat_details = [CategoryDetail(name=c, why="تصفح القسم") for c in cats]
            
            return ChatResponse(
                session_id=session_id,
                intent=IntentType.CATALOG_BROWSING,
                answer=answer,
                courses=[],
                projects=[],
                skill_groups=[],
                catalog_browsing=CatalogBrowsingData(categories=cat_details, next_question="تختار أي قسم؟"),
                learning_plan=None,
                dashboard=None,
                error=None,
                request_id=request_id,
                ask=ChoiceQuestion(question="تحب تختار قسم منهم ولا تحب أساعدك تختار على حسب هدفك؟", choices=[c.name for c in cat_details]),
                followup_question=None
            )

        # --- V17 RULE 3: Disambiguation Resolution ---
        # If we offered categories last turn and user replied with one of them, treat as category selection
        offered_categories = session_state.get("offered_categories", [])
        if offered_categories:
            user_selection = None
            user_msg_norm = data_loader.normalize_category(request.message)
            for offered in offered_categories:
                offered_norm = data_loader.normalize_category(offered)
                # Check if user message is the category OR contains it
                if user_msg_norm == offered_norm or offered_norm in user_msg_norm:
                    user_selection = offered
                    break
            if user_selection:
                logger.info(f"[{request_id}] V17 Disambiguation Resolution: User selected '{user_selection}'")
                # Clear offered list (consumed)
                session_state["offered_categories"] = []
                # Override intent to COURSE_SEARCH with selected category
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH, 
                    topic=user_selection, 
                    confidence=1.0, 
                    needs_courses=True,
                    role=None,
                    specific_course=user_selection
                )
                # Skip the disambiguation block by marking we have a specific topic

        # --- EXPLORATION FLOW (V1.1 State-Aware) ---
        if intent_result.intent in [IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP]:
             logger.info(f"[{request_id}] Fast Path: EXPLORATION FLOW")
             
             # Call new handler logic via builder
             answer, projects, selected, skills, plan, dash, all_rel, cat_b, mode, f_q, ref_intent, state_updates = await response_builder.build(
                intent_result=intent_result,
                courses=[],
                skill_result=SkillValidationResult(validated_skills=[]),
                user_message=request.message,
                context=session_state,
                semantic_result=SemanticResult(primary_domain="General", is_in_catalog=True)
             )
             
             # Override Intent if Builder transitioned (e.g. to COURSE_SEARCH)
             final_intent = ref_intent if ref_intent else intent_result.intent
             
             # ✅ IMMEDIATE RETRIEVAL (V2.0 Fix): If flow transitioned to COURSE_SEARCH, run pipeline NOW
             courses = []
             skill_groups = []
             
             if str(final_intent) == "COURSE_SEARCH" and state_updates and (state_updates.get("topic") or state_updates.get("track")):
                 logger.info(f"[{request_id}] Exploration Flow -> Immediate Retrieval Triggered for {state_updates.get('topic')}")
                 
                 # Update intent result for pipeline
                 intent_result.intent = IntentType.COURSE_SEARCH
                 intent_result.topic = state_updates.get("topic")
                 intent_result.needs_courses = True
                 
                 # Run Pipeline
                 skill_result, courses = await run_course_search_pipeline(
                     intent_result,
                     SemanticResult(primary_domain=intent_result.topic, is_in_catalog=True),
                     request_id,
                     session_state,
                     False,
                     request.message
                 )
                 
                 # Re-build answer with courses if needed, or just append courses to response
                 # We kept 'answer' from builder which says "Here are courses for X", so just attach courses.
             
             # Apply State Updates
             if state_updates:
                 conversation_memory.add_assistant_message(session_id, answer, intent=str(final_intent), state_updates=state_updates)
             else:
                 conversation_memory.add_assistant_message(session_id, answer, intent=str(final_intent))

             return ChatResponse(
                session_id=session_id,
                intent=final_intent,
                answer=answer,
                courses=courses,
                projects=projects,
                skill_groups=skills,
                learning_plan=plan,
                dashboard=dash,
                request_id=request_id,
                ask=f_q if isinstance(f_q, ChoiceQuestion) else None,
                followup_question=f_q if isinstance(f_q, str) else None,
                meta={"flow": "exploration_v2", "transitioned": str(final_intent) != str(intent_result.intent)}
             )

        # --- DETERMINISTIC FAST PATH REMOVED (V18 Fix) ---
        # We removed the early-return for broad topics ("programming") to ensure successful retrieval.
        pass

        # --- LLM-FREE FAST PATH: PAGINATION / MORE (V13/V15/Addendum v1.1) ---
        cached_ids = session_state.get("all_relevant_course_ids", [])
        pagination_offset = session_state.get("pagination_offset", 0)
        
        # V1.1: Strict Follow-Up Logic (Never re-search)
        is_follow_up_intent = intent_result.intent == IntentType.FOLLOW_UP
        is_implicit_more = any(t in request.message.lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])
        
        # If explicit FOLLOW_UP or implicit more with cache -> Serve from cache
        if (is_follow_up_intent or is_implicit_more) and cached_ids:
            logger.info(f"[{request_id}] Production Fast-Path: Serving cached results for Follow-Up.")
            
            # Increment offset
            new_offset = pagination_offset + 5 # Batch of 5 (Standard)
            # If we reached the end, loop back or stop? User says "increase offset". 
            # If > len, we should probably warn or wrap. Let's wrap for now to ensure results.
            if new_offset >= len(cached_ids):
                new_offset = 0 # Loop back for demo/robustness
                
            state_updates = {"pagination_offset": new_offset}
            next_batch_ids = cached_ids[new_offset : new_offset + 5]
            
            courses = [retriever.get_course_details(cid) for cid in next_batch_ids if retriever.get_course_details(cid)]
            
            # Mock objects for fast response
            mock_semantic = SemanticResult(primary_domain="General", search_axes=[])
            mock_skills = SkillValidationResult(validated_skills=session_state.get("last_skills", []))
            
            # Bypass ResponseBuilder complex logic if possible, or use it with minimal context
            # We use response_builder but with a specific "FOLLOW_UP" mode implicity through the intent
            answer, projects, selected, skills, plan, dash, all_rel, cat_b, mode, f_q, ref_intent, _ = await response_builder.build(
                intent_result=intent_result,
                courses=courses,
                skill_result=mock_skills,
                user_message=request.message,
                context=session_state,
                semantic_result=mock_semantic
            )
            
            # Add metadata for eval
            meta = {
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "follow_up": True,
                "error": None
            }
            
            conversation_memory.add_assistant_message(session_id, answer, intent=IntentType.COURSE_SEARCH.value, state_updates=state_updates)
            return ChatResponse(
                session_id=session_id,
                intent=IntentType.COURSE_SEARCH,
                answer=answer,
                courses=selected,
                all_relevant_courses=all_rel,
                skill_groups=skills,
                request_id=request_id,
                ask=f_q if isinstance(f_q, ChoiceQuestion) else None,
                followup_question=f_q if isinstance(f_q, str) else None,
                meta=meta
            )

        # Step 2: Semantic Layer (Deep Understanding)
        previous_topic = session_state.get("last_role") or session_state.get("last_topic")
        
        if semantic_result_override:
            semantic_result = SemanticResult(**semantic_result_override, extracted_skills=[])
        else:
             # V1.1 LATENCY FIX: Skip Semantic Layer for General QA to prevent "LLM multiple hops" 429 errors
             if intent_result.intent == IntentType.GENERAL_QA:
                 semantic_result = SemanticResult(primary_domain="General", is_in_catalog=True)
                 logger.info(f"[{request_id}] Fast-Path: Skipped Semantic Layer for GENERAL_QA")
             else:
                semantic_result = await semantic_layer.analyze(
                    request.message, 
                    intent_result, 
                    previous_topic=previous_topic
                )
        
        # Honesty Guard: Applies ONLY to COURSE_SEARCH, COURSE_DETAILS, LEARNING_PATH (Addendum v1.1)
        honesty_guard_intents = [IntentType.COURSE_SEARCH, IntentType.COURSE_DETAILS, IntentType.LEARNING_PATH]
        if intent_result.intent in honesty_guard_intents and not semantic_result.is_in_catalog:
            logger.warning(f"[{request_id}] Honesty Guard Triggered: {semantic_result.missing_domain or semantic_result.primary_domain} is NOT in catalog. Returning SAFE_FALLBACK.")
            intent_result.intent = IntentType.SAFE_FALLBACK
            intent_result.needs_courses = False
             
        # V6: Robust Pagination & Context Persistence
        state_updates = {}
        is_more_request = any(t in request.message.lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])
        cached_ids = session_state.get("all_relevant_course_ids", [])
        
        # V12: Increment offset if it's a "more" request
        pagination_offset = session_state.get("pagination_offset", 0)
        if is_more_request:
             pagination_offset += 5
             state_updates["pagination_offset"] = pagination_offset
             logger.info(f"[{request_id}] 'More' request. Incremented offset to {pagination_offset}")

        # Determine if we can skip retrieval (More request with cache)
        can_use_cache = is_more_request and cached_ids and (intent_result.intent in [IntentType.COURSE_SEARCH, IntentType.CAREER_GUIDANCE])
        
        if can_use_cache:
            logger.info(f"[{request_id}] 'More' request detected. Using {len(cached_ids)} cached results.")
            # Load courses from cache IDs
            courses = []
            for cid in cached_ids[pagination_offset:]:
                c = retriever.get_course_details(cid)
                if c: courses.append(c)
            filtered_courses = courses
            # Use cached skills context
            skill_result = SkillValidationResult(validated_skills=session_state.get("last_skills", []))
            
        else:
            # --- V21 FIX: LEARNING_PATH CONTEXT RECOVERY (Before Pipeline) ---
            if intent_result.intent == IntentType.LEARNING_PATH:
                 # 1. Recover Topic if missing
                 if not intent_result.topic:
                      intent_result.topic = session_state.get("last_topic") or session_state.get("last_search_topic")
                      if intent_result.topic:
                           logger.info(f"[{request_id}] Context Recovery: Inferred topic '{intent_result.topic}' from session.")
                 
                 # 2. Reuse Courses (Best UX)
                 # If we have relevant courses in session, reuse them instead of searching again
                 last_courses_ids = session_state.get("all_relevant_course_ids", [])
                 if last_courses_ids and intent_result.topic:
                      # Quick fetch from cache
                      filtered_courses = [retriever.get_course_details(cid) for cid in last_courses_ids[:5] if retriever.get_course_details(cid)]
                      filtered_courses = [c for c in filtered_courses if c] # filter Nones
                      skill_result = SkillValidationResult(validated_skills=[]) # Validated skills not strictly needed for plan generation if we have courses
                      skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA, IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP, IntentType.LEARNING_PATH] # Skip search now
                 else:
                      # No courses? We must run search pipeline if we have a topic
                      if intent_result.topic:
                           skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA, IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP]
                      else:
                           # No topic + No courses => logic in Builder will ask question
                           skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA, IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP, IntentType.LEARNING_PATH]
            else:
                 # Standard skip list
                 skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA, IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP]
            
            if intent_result.intent in skip_search_intents:
                 logger.info(f"[{request_id}] Skipping Course Search Pipeline for {intent_result.intent.value}")
                 skill_result = SkillValidationResult(validated_skills=[])
                 filtered_courses = []
                 # Mock semantic for simple response
                 semantic_result = SemanticResult(primary_domain="General", is_in_catalog=True)
                 
            else:
                # UNIFIED PIPELINE (No Early Returns)
                logger.info(f"[{request_id}] COURSE_SEARCH pipeline executed")
                skill_result, filtered_courses = await run_course_search_pipeline(
                    intent_result,
                    semantic_result,
                    request_id,
                    session_state,
                    is_more_request,
                    request.message
                )
            
            # Cache full list
            state_updates["all_relevant_course_ids"] = [c.course_id for c in filtered_courses]
            if not is_more_request:
                state_updates["pagination_offset"] = 0
                
                # --- V20: Persist Search Context for Follow-ups ---
                if intent_result.intent == IntentType.COURSE_SEARCH:
                     # Prefer specific user topic (JavaScript) over broad domain (Programming) for plan generation
                     state_updates["last_topic"] = intent_result.topic or semantic_result.primary_domain
                     state_updates["last_role"] = intent_result.role
                     if semantic_result.user_level:
                          state_updates["last_level_preference"] = semantic_result.user_level
                     logger.info(f"[{request_id}] Persisted Context: Topic={state_updates.get('last_topic')} Level={state_updates.get('last_level_preference')}")

        # Step 6: Response Builder
        if semantic_result.brief_explanation:
             session_state["brief_explanation"] = semantic_result.brief_explanation
        
        # Pass categories for discovery
        available_categories = data_loader.get_all_categories()
        
        # --- REQUIREMENT: SAFE UNPACKING (V21) ---
        def normalize_builder_output(out):
            # expected 12 elements
            # (answer, projects, courses, skill_groups, learning_plan, dashboard, all_rel, browsing, mode, f_q, intent, updates)
            default = ("", [], [], [], None, None, [], None, "answer_only", None, intent_result.intent.value, {})
            
            if out is None: return default
            
            if isinstance(out, tuple):
                current_len = len(out)
                if current_len == 12:
                    return out
                elif current_len < 12:
                    # Pad with defaults
                    return out + default[current_len:]
                else:
                    # Truncate
                    return out[:12]
            return default

        raw_builder_output = await response_builder.build(
            intent_result=intent_result,
            courses=filtered_courses,
            skill_result=skill_result,
            user_message=request.message,
            context=session_state,
            semantic_result=semantic_result
        )
        
        build_result = normalize_builder_output(raw_builder_output)
        answer, projects, selected_courses, skill_groups, learning_plan, dashboard, all_rel, catalog_browsing, mode, f_question, refined_intent, flow_state_updates = build_result
        
        # V3: Consistency Check (Anti-Hallucination)
        if selected_courses:
            is_consistent, inconsistencies = consistency_checker.check(answer, selected_courses)
            if not is_consistent:
                logger.warning(f"[{request_id}] Consistency Check Failed: {inconsistencies}")
                # We could regenerate, but for now we just log.
        
        # Step 7: Update Memory
        # Extract skills to persist context
        new_skills = skill_result.validated_skills
        if new_skills:
            state_updates["last_skills"] = new_skills
        
        if intent_result.role:
            state_updates["last_role"] = intent_result.role

        if intent_result.intent == IntentType.COURSE_DETAILS:
             if hasattr(intent_result, 'specific_course'):
                 state_updates["last_course_viewed"] = intent_result.specific_course

        # V16: Persist topic key for semantic search consistency
        if semantic_result.primary_domain:
             state_updates["topic_key"] = semantic_result.primary_domain
             
        # V18: Persist context for FOLLOW_UP requirements
        # Save last search parameters if we found courses
        if intent_result.intent == IntentType.COURSE_SEARCH and selected_courses:
             state_updates["last_topic"] = intent_result.specific_course or intent_result.slots.get("topic") or semantic_result.primary_domain
             state_updates["last_query"] = request.message
             logger.info(f"[{request_id}] Persisted search context: {state_updates['last_topic']}")

        # Helper to merge updates
        final_updates = state_updates.copy() if state_updates else {}
        if flow_state_updates: final_updates.update(flow_state_updates)
        
        conversation_memory.add_assistant_message(
            session_id,
            answer,
            intent=refined_intent or intent_result.intent.value,
            skills=new_skills,
            state_updates=final_updates
        )
        
        
        process_time = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Request completed in {process_time:.2f}ms")
        
        # FOLLOW_UP Normalization: API always returns COURSE_SEARCH for follow-up queries
        # This ensures UI stability while preserving internal context
        response_intent = refined_intent or intent_result.intent
        is_follow_up = (response_intent == IntentType.FOLLOW_UP)
        if response_intent == IntentType.FOLLOW_UP:
            response_intent = IntentType.COURSE_SEARCH
            logger.info(f"[{request_id}] Normalized FOLLOW_UP -> COURSE_SEARCH in response")
        
        # Metadata construction
        meta = {
            "latency_ms": round(process_time, 2),
            "follow_up": is_follow_up,
            "error": None
        }

        # Language Lock (Rule 0)
        is_ar = data_loader.is_arabic(request.message)
        lang = "ar" if is_ar else "en"

        # Map f_question to ask (Rule 7)
        ask_obj = None
        if isinstance(f_question, ChoiceQuestion):
            ask_obj = f_question
        elif isinstance(f_question, str) and f_question:
            ask_obj = ChoiceQuestion(question=f_question, choices=[])

        # Map flow_state_updates (Rule 2 & 7)
        fsu = None
        if flow_state_updates:
            fsu = FlowStateUpdates(
                active_flow=flow_state_updates.get("active_flow"),
                topic=flow_state_updates.get("topic") or flow_state_updates.get("last_topic") or flow_state_updates.get("exploration", {}).get("domain"),
                track=flow_state_updates.get("track") or flow_state_updates.get("last_role"),
                duration=flow_state_updates.get("duration") or flow_state_updates.get("exploration", {}).get("time"),
                time_per_day=flow_state_updates.get("time_per_day") or flow_state_updates.get("exploration", {}).get("time_per_day"),
                exploration=flow_state_updates.get("exploration")
            )

        return ChatResponse(
            session_id=session_id,
            request_id=request_id,
            intent=response_intent,
            language=lang,
            answer=answer,
            ask=ask_obj,
            courses=selected_courses,
            projects=projects,
            learning_plan=learning_plan,
            flow_state_updates=fsu,
            all_relevant_courses=all_rel,
            skill_groups=skill_groups,
            catalog_browsing=catalog_browsing,
            dashboard=dashboard,
            meta=meta
        )

    except Exception as e:
        logger.error(f"[{request_id}] Pipeline Error: {e}", exc_info=True)
        # Zedny Rule: Never say "Technical Error"
        answer = "تمام، بس محتاج أعرف أكتر عن هدفك حالياً عشان أقدر أساعدك؟" if data_loader.is_arabic(request.message) else "Got it, but could you tell me a bit more about your goal so I can guide you better?"
        
        return ChatResponse(
            session_id=session_id,
            intent=IntentType.GENERAL_QA,
            answer=answer,
            courses=[],
            error=ErrorDetail(message=str(e), code="PIPELINE_ERROR"),
            request_id=request_id
        )

# Run with: uvicorn main:app --reload
