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
)
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
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
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
        from semantic_search import semantic_search as _semantic_search
        semantic_search = _semantic_search
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
            success=False,
            intent=IntentType.SAFE_FALLBACK,
            message=msg,
            courses=[],
            categories=[],
            errors=[f"{type(exc).__name__}: {str(exc)}"],
            language="ar" if is_ar else "en",
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

        conversation_memory.add_user_message(session_id, f"[Uploaded CV: {file.filename}]")

        session_state = conversation_memory.get_session_state(session_id)
        session_state["last_intent"] = IntentType.CV_ANALYSIS

        user_message = f"Analyze this CV content: {extracted_text[:4000]}"

        intent_result = IntentResult(intent=IntentType.CV_ANALYSIS)

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
        conversation_memory.update_session_state(session_id, session_state)

        courses = []

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

        conversation_memory.add_assistant_message(
            session_id,
            chat_res.message,
            intent=IntentType.CV_ANALYSIS,
            skills=skill_result.validated_skills
        )

        return chat_res

    except Exception as e:
        logger.error(f"CV Upload Error: {e}", exc_info=True)
        return ChatResponse(
            success=False,
            session_id=session_id,
            intent=IntentType.CV_ANALYSIS,
            message="حصلت مشكلة أثناء رفع الملف. جرّب PDF أو DOCX، أو ابعتلي هدفك الوظيفي وأنا أساعدك فورًا.",
            courses=[],
            categories=[],
            errors=[str(e)],
            request_id=request_id,
            language="ar",
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
        IntentType.CAREER_GUIDANCE,
        IntentType.LEARNING_PATH,
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
    """Main chat endpoint implementing the 7-step RAG pipeline."""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"[{request_id}] Processing CHAT request | Session: {session_id} | Msg: {request.message[:50]}...")

    conversation_memory.add_user_message(session_id, request.message)
    session_state = conversation_memory.get_session_state(session_id)

    semantic_result_override = None

    # ---------------------------
    # STATE-BASED FOLLOW-UP RESOLVER (Production)
    # Supports: "- Choice", "1", "ماشي/ok", "اعرض"
    # ---------------------------
    raw_msg = (request.message or "").strip()
    msg_clean = raw_msg.lstrip("-•* ").strip()
    msg_lower = msg_clean.lower()

    pending = session_state.get("pending_question")  # {kind, question, choices/options, on_select}
    yes_words = {"ماشي","تمام","اه","أه","ايوه","أيوة","ok","okay","yes","yep"}
    show_words = {"اعرض","وريني","show","عرض"}

    resolved_intent_result = None

    if pending:
        kind = pending.get("kind")

        # (1) Choice selection
        if kind == "choices":
            choices = pending.get("choices", [])
            norm = [c.strip().lower() for c in choices]
            if msg_lower in norm:
                selected = choices[norm.index(msg_lower)]

                on_select = pending.get("on_select", {})  # {"intent": "...", "topic": "..."} or {"mode":"topic_from_selected"}
                session_state["pending_question"] = None

                # Default behavior: selecting a choice means user wants courses for that selection
                # If parent_topic exists, we can use selected as subtrack
                parent = on_select.get("parent_topic")
                topic_mode = on_select.get("topic_mode", "selected")

                topic = selected
                if topic_mode == "selected_or_parent" and parent:
                    # topic becomes parent, but keep selected in last_subtopic
                    session_state["last_subtopic"] = selected
                    topic = parent

                resolved_intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=topic,
                    specific_course=selected,
                    needs_courses=True,
                    confidence=1.0
                )

        # (2) Numeric selection
        elif kind == "numeric" and msg_clean.isdigit():
            idx = int(msg_clean) - 1
            opts = pending.get("options", [])
            if 0 <= idx < len(opts):
                selected = opts[idx]
                session_state["pending_question"] = None

                resolved_intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=selected,
                    needs_courses=True,
                    confidence=1.0
                )

        # (3) Yes/No confirmation
        elif kind == "yesno" and msg_lower in yes_words:
            yes_action = pending.get("yes_action", "SHOW_COURSES")  # SHOW_COURSES | MAKE_PLAN | PROJECTS
            session_state["pending_question"] = None

            last_topic = session_state.get("last_topic") or pending.get("topic")

            if yes_action == "SHOW_COURSES":
                resolved_intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=last_topic,
                    needs_courses=True,
                    confidence=1.0
                )
            else:
                # Plan/Projects go through CAREER_GUIDANCE (still within 6 intents)
                resolved_intent_result = IntentResult(
                    intent=IntentType.CAREER_GUIDANCE,
                    topic=last_topic,
                    needs_explanation=True,
                    confidence=1.0
                )

    # (4) "اعرض" without pending question => treat as follow-up to show courses for last_topic
    if resolved_intent_result is None and msg_lower in show_words:
        last_topic = session_state.get("last_topic")
        if last_topic:
            resolved_intent_result = IntentResult(
                intent=IntentType.COURSE_SEARCH,
                topic=last_topic,
                needs_courses=True,
                confidence=0.95
            )

    # Persist session_state if we consumed pending
    conversation_memory.update_session_state(session_id, session_state)


    # --- PATCH 4: Sales Manager + Guidance ---
    msg_l = (request.message or "").lower()
    is_mgr = any(k in msg_l for k in ["مدير","manager","lead","قيادة"])
    is_sales = any(k in msg_l for k in ["مبيعات","sales","selling"])

    if is_mgr and is_sales:
        session_state["last_topic"] = "Sales Management"
        session_state["last_intent"] = "CAREER_GUIDANCE"
        session_state["pending_question"] = {
            "kind": "choices",
            "question": "تحب أساعدك بإيه دلوقتي؟",
            "choices": ["كورسات من الكتالوج", "خطة مذاكرة", "أفكار مشاريع/تمارين"],
            "on_select": {"topic_mode": "selected"}
        }
        conversation_memory.update_session_state(session_id, session_state)

        return ChatResponse(
            intent=IntentType.CAREER_GUIDANCE,
            answer=(
                "تمام ✅ عشان تبقى مدير مبيعات ناجح ركّز على: "
                "Pipeline & Forecasting، Coaching للفريق، KPIs، Negotiation، CRM & Process.\n\n"
                "تحب أساعدك بإيه دلوقتي؟"
            ),
            one_question=OneQuestion(
                question="اختار واحد:",
                choices=session_state["pending_question"]["choices"]
            ),
            language="ar",
            session_id=session_id,
            request_id=request_id
        )

    # --- CHOICE RESOLUTION (supports "- Choice") ---
    last_q = session_state.get("last_one_question")
    raw_msg = (request.message or "").strip()

    # normalize "- Social Media" -> "Social Media"
    msg_clean = raw_msg.lstrip("-•* ").strip()
    msg_lower_clean = msg_clean.lower()
    intent_result = None

    if last_q and msg_clean:
        choices = last_q.get("choices", [])
        choices_norm = [c.strip().lower() for c in choices]

        if msg_lower_clean in choices_norm:
            selected = choices[choices_norm.index(msg_lower_clean)]
            logger.info(f"[{request_id}] Choice Resolution: '{raw_msg}' -> '{selected}'")

            # consume it
            session_state["last_one_question"] = None
            conversation_memory.update_session_state(session_id, session_state)

            # Route deterministically based on selected choice
            marketing_subtracks = {"digital marketing", "social media", "content marketing", "content creation", "performance ads", "brand marketing", "analytics", "seo & sem"}
            data_paths = {"data analysis", "machine learning", "data engineering", "power bi / excel", "big data"}
            sales_paths = {"b2b sales", "cold calling", "closing deals", "sales management", "negotiation"}
            programming_paths = {"web development", "mobile apps", "python & ai", "backend systems", "devops"}

            sel_lower = selected.strip().lower()

            if sel_lower in marketing_subtracks:
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic="Marketing" if sel_lower == "marketing" else selected,
                    needs_courses=True,
                    confidence=1.0
                )
            elif sel_lower in data_paths:
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=selected,
                    needs_courses=True,
                    confidence=1.0
                )
            elif sel_lower in sales_paths:
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=selected,
                    needs_courses=True,
                    confidence=1.0
                )
            elif sel_lower in programming_paths:
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=selected,
                    needs_courses=True,
                    confidence=1.0
                )
            else:
                # generic category selection
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=selected,
                    needs_courses=True,
                    confidence=1.0
                )

    try:
        from fastapi.responses import JSONResponse
        msg = (request.message or "").strip()
        msg_lower = msg.lower()

        # --- HARD OVERRIDE: Sales Manager ---
        manager_keywords = ["مدير", "إدارة", "قيادة", "lead", "manager", "leadership"]
        sales_keywords = ["sales", "مبيعات", "بيع", "selling"]
        
        # --- HARD OVERRIDE: Data Analysis ---
        da_keywords = ["data analysis", "تحليل بيانات", "analyst", "محلل بيانات", "analysis"]
        is_da = any(k in msg_lower for k in da_keywords)
        
        if is_da and not intent_result:
             logger.info(f"[{request_id}] HARD OVERRIDE: Data Analysis -> CAREER_GUIDANCE")
             # JSONResponse is already imported at top of try block
             message = "ممتاز! تحليل البيانات (Data Analysis) بيعتمد على 4 ركائز أساسية: (1) Excel و Statistics (2) SQL لقواعد البيانات (3) Power BI للـ Visualization (4) Python للتحليل المتقدم. تحب نبدأ بأي واحدة فيهم؟"
             chat_res = ChatResponse(
                success=True,
                intent=IntentType.CAREER_GUIDANCE,
                message=message,
                language="ar",
                categories=["Data Analysis", "SQL", "Power BI", "Python", "Excel"],
                meta={"flow":"deterministic_data_analysis"}
            )
             return JSONResponse(status_code=200, content=chat_res.model_dump(by_alias=True))

        if not intent_result and any(k in msg_lower for k in manager_keywords) and any(k in msg_lower for k in sales_keywords):
            logger.info(f"[{request_id}] HARD OVERRIDE: Sales Manager -> CAREER_GUIDANCE + courses")
            
            # Fetch courses directly (Show don't ask)
            try:
                sales_courses = retriever.browse_by_category("Sales") or []
                lead_courses = retriever.browse_by_category("Leadership & Management") or []
                # Combine top 3 from each
                suggested_courses = sales_courses[:3] + lead_courses[:3]
            except Exception as e:
                logger.error(f"Failed to fetch courses for override: {e}")
                suggested_courses = []

            # Deterministic response with courses
            message = "عشان تكون مدير مبيعات ناجح، محتاج تجمع بين مهارات البيع والقيادة. دي أهم الكورسات اللي هتساعدك تطور المهارات دي:"

            chat_res = ChatResponse(
                success=True,
                intent=IntentType.CAREER_GUIDANCE,
                message=message,
                language="ar",
                categories=["Sales", "Leadership & Management"],
                courses=suggested_courses,
                meta={"flow":"deterministic_sales_manager"}
            )
            return JSONResponse(status_code=200, content=chat_res.model_dump(by_alias=True))

        # --- HARD RULE: React / SQL / Python / Tech Skills ---
        tech_keywords = [
            "react", "sql", "python", "javascript", "node", "java", "frontend", "backend",
            "بايثون", "رياكت", "سيكوال", "جافا", "فرونت", "باك", "تحليل", "analysis"
        ]
        if not intent_result:
            for tech in tech_keywords:
                if tech in msg_lower:
                    logger.info(f"[{request_id}] HARD RULE: Tech Skill '{tech}' -> CAREER_GUIDANCE")
                    # Map Arabic keyword to English Topic if needed
                    topic_map = {
                        "بايثون": "Python",
                        "رياكت": "React",
                        "سيكوال": "SQL",
                        "جافا": "Java",
                        "جافا سكربت": "JavaScript"
                    }
                    final_topic = topic_map.get(tech, tech.title())
                    
                    intent_result = IntentResult(
                        intent=IntentType.CAREER_GUIDANCE,
                        topic=final_topic,
                        needs_explanation=True,
                        needs_courses=False,
                        confidence=1.0
                    )
                    break

        # Step 1: Intent Router
        if not intent_result:
            intent_result = resolved_intent_result or await intent_router.route(request.message, session_state)

        # --- PATCH 3: Undecided / Lost ---
        undecided = ["تايه","محتار","مش عارف","مش عارف اختار","i don't know","help me choose"]

        if any(w in (request.message or "").lower() for w in undecided):
            # لو ذكر مجال معروف
            msg_l = (request.message or "").lower()
            if "marketing" in msg_l or "تسويق" in msg_l:
                session_state["last_topic"] = "Marketing"
                # اسأله يحدد اتجاه داخل الماركتنج
                session_state["pending_question"] = {
                    "kind": "choices",
                    "question": "تمام 👌 تحب تبدأ أنهي اتجاه في Marketing؟",
                    "choices": ["Digital Marketing", "Social Media", "Content Marketing", "Performance Ads", "Brand Marketing"],
                    "on_select": {"topic_mode": "selected_or_parent", "parent_topic": "Marketing"}
                }
                conversation_memory.update_session_state(session_id, session_state)

                return ChatResponse(
                    intent=IntentType.CAREER_GUIDANCE,
                    answer="تمام 👌 تحب تبدأ أنهي اتجاه في Marketing؟",
                    one_question=OneQuestion(
                        question="اختار اتجاه واحد:",
                        choices=session_state["pending_question"]["choices"]
                    ),
                    language="ar",
                    session_id=session_id,
                    request_id=request_id
                )

            # لو ما ذكرش مجال
            session_state["pending_question"] = {
                "kind": "choices",
                "question": "تمام 👌 اختر مجال واحد نبدأ بيه:",
                "choices": ["Marketing", "Sales", "Data Science", "Programming", "Leadership & Management"],
                "on_select": {"topic_mode": "selected"}
            }
            conversation_memory.update_session_state(session_id, session_state)

            return ChatResponse(
                intent=IntentType.SAFE_FALLBACK,
                answer="تمام 👌 اختر مجال واحد نبدأ بيه:",
                one_question=OneQuestion(
                    question="اختار مجال:",
                    choices=session_state["pending_question"]["choices"]
                ),
                language="ar",
                session_id=session_id,
                request_id=request_id
            )

        # --- ZEDNY PRODUCTION RULES (Locking & Fallback) ---
        exploration_state = session_state.get("exploration", {})
        active_f = session_state.get("active_flow")
        stage = (exploration_state or {}).get("stage")

        if stage == "locked":
            chosen_domain = exploration_state.get("chosen_domain")
            msg = (request.message or "").lower()
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
            # IMPORTANT: do NOT use non-existing enum EXPLORATION_FOLLOWUP unless it exists
            # safest behavior: treat it as SAFE_FALLBACK (ask a focused choice question)
            logger.info(f"[{request_id}] Exploration Flow Active: Force SAFE_FALLBACK")
            intent_result.intent = IntentType.SAFE_FALLBACK
            intent_result.confidence = 1.0
            intent_result.needs_courses = False

        else:
            undecided_triggers = ["مش عارف", "تايه", "محتار", "ساعدني", "مش عارف اختار", "i don't know", "help me choose"]
            msg_lower = (request.message or "").lower()
            if (("مدير" in msg_lower or "manager" in msg_lower) and ("مبيعات" in msg_lower or "sales" in msg_lower)):
                logger.info(f"[{request_id}] Patch 4: Sales Manager Manual Override")
                intent_result.intent = IntentType.CAREER_GUIDANCE
                intent_result.topic = "Sales Management"
                intent_result.needs_courses = True
                intent_result.confidence = 1.0
            
            elif any(kw in msg_lower for kw in undecided_triggers):
                # FIX: no EXPLORATION intent — use SAFE_FALLBACK or CAREER_GUIDANCE
                logger.info(f"[{request_id}] Rule 3 Trigger: Force SAFE_FALLBACK (was EXPLORATION)")
                intent_result.intent = IntentType.SAFE_FALLBACK
                intent_result.confidence = 1.0
                intent_result.needs_courses = False

        logger.info(f"[{request_id}] Final Intent: {_safe_intent_value(intent_result.intent)}")

        # --- V17 RULE 3: Disambiguation Resolution ---
        offered_categories = session_state.get("offered_categories", [])
        if offered_categories:
            user_selection = None
            user_msg_norm = data_loader.normalize_category(request.message)
            for offered in offered_categories:
                offered_norm = data_loader.normalize_category(offered)
                if user_msg_norm == offered_norm or offered_norm in user_msg_norm:
                    user_selection = offered
                    break
            if user_selection:
                logger.info(f"[{request_id}] V17 Disambiguation Resolution: User selected '{user_selection}'")
                session_state["offered_categories"] = []
                intent_result = IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=user_selection,
                    confidence=1.0,
                    needs_courses=True,
                    role=None,
                    specific_course=user_selection
                )

        # --- PATCH 1: Deterministic SAFE_FALLBACK ---
        if intent_result.intent == IntentType.SAFE_FALLBACK:
            from fastapi.responses import JSONResponse
            from models import OneQuestion

            logger.info(f"[{request_id}] Patch 1: Deterministic SAFE_FALLBACK")
            is_ar = _is_arabic_text(request.message)
            msg_lower = (request.message or "").lower()

            guess_map = {
                "marketing": "Marketing", "تسويق": "Marketing", "ماركتنج": "Marketing",
                "sales": "Sales", "مبيعات": "Sales", "selling": "Sales",
                "data": "Data Science", "بيانات": "Data Science", "science": "Data Science", "analysis": "Data Science",
                "programming": "Programming", "برمجة": "Programming", "development": "Programming", "software": "Programming", "code": "Programming", "coding": "Programming"
            }
            
            guessed = None
            for key, val in guess_map.items():
                if key in msg_lower:
                    guessed = val
                    break

            if guessed == "Marketing":
                question = OneQuestion(
                    question="تسويق بحر كبير! تحب نركز على إيه؟" if is_ar else "Which marketing track?",
                    choices=["Digital Marketing", "Social Media", "Content Creation", "SEO & SEM", "Analytics"]
                )
                domain_list = "\n".join([f"- {d}" for d in question.choices])
                message = f"تمام 👌 التسويق مجالاته كتير، اختار الأقرب ليك:\n\n{domain_list}" if is_ar else f"Marketing is broad! Pick a focus:\n\n{domain_list}"
                categories = ["Marketing"]
            
            elif guessed == "Sales":
                 question = OneQuestion(
                    question="عايز تقوي نفسك في إيه في المبيعات؟" if is_ar else "Which sales skill?",
                    choices=["B2B Sales", "Cold Calling", "Closing Deals", "Sales Management", "Negotiation"]
                )
                 domain_list = "\n".join([f"- {d}" for d in question.choices])
                 message = f"المبيعات شطارة! ركز على مهارة معينة:\n\n{domain_list}" if is_ar else f"Sales involves many skills. Choose one:\n\n{domain_list}"
                 categories = ["Sales"]

            elif guessed == "Data Science":
                 question = OneQuestion(
                    question="مجال البيانات واسع، حابب تبدأ فين؟" if is_ar else "Which data track?",
                    choices=["Data Analysis", "Machine Learning", "Data Engineering", "Power BI / Excel", "Big Data"]
                )
                 domain_list = "\n".join([f"- {d}" for d in question.choices])
                 message = f"تمام، عالم البيانات كبير. ابدأ باختيار مسار:\n\n{domain_list}" if is_ar else f"Data is a big field. Pick a path:\n\n{domain_list}"
                 categories = ["Data Science"]

            elif guessed == "Programming":
                 question = OneQuestion(
                    question="البرمجة اتجاهاتها كتير، ميال لإيه؟" if is_ar else "Which coding path?",
                    choices=["Web Development", "Mobile Apps", "Python & AI", "Backend Systems", "DevOps"]
                )
                 domain_list = "\n".join([f"- {d}" for d in question.choices])
                 message = f"حلو جداً، حدد تراك عشان أجبلك الكورسات المناسبة:\n\n{domain_list}" if is_ar else f"Coding has many paths. Choose yours:\n\n{domain_list}"
                 categories = ["Programming"]
            else:
                question = OneQuestion(
                    question="تحب تبدأ في أي مجال؟" if is_ar else "Which domain interests you?",
                    choices=["Marketing", "Sales", "Data Science", "Programming", "Leadership & Management"]
                )
                domain_list = "\n".join([f"- {d}" for d in question.choices])
                message = f"تمام 👌 علشان أرشدك صح، اختار مجال واحد نبدأ بيه:\n\n{domain_list}" if is_ar else f"Great! To guide you better, please pick a domain:\n\n{domain_list}"
                categories = ["Marketing", "Sales", "Data Science", "Programming", "Leadership & Management"]

            # Save choice context
            session_state["last_one_question"] = {
                "question": question.question,
                "choices": question.choices
            }
            conversation_memory.update_session_state(session_id, session_state)

            chat_res = ChatResponse(
                success=True,
                intent=IntentType.SAFE_FALLBACK,
                message=message,
                courses=[],
                categories=categories,
                errors=[],
                language="ar" if is_ar else "en",
                one_question=question,
                meta={"flow": "deterministic_safe_fallback"},
                session_id=session_id,
                request_id=request_id
            )
            return JSONResponse(status_code=200, content=chat_res.model_dump(by_alias=True))

        # --- PATCH 2: Deterministic CATALOG_BROWSE ---
        if intent_result.intent == IntentType.CATALOG_BROWSE:
            from fastapi.responses import JSONResponse
            logger.info(f"[{request_id}] Patch 2: Deterministic CATALOG_BROWSE")
            all_cats = data_loader.get_all_categories()
            if not all_cats:
                all_cats = ["Marketing", "Sales", "Data Science", "Programming", "Design", "Leadership & Management"]

            is_ar = _is_arabic_text(request.message)
            chat_res = ChatResponse(
                success=True,
                intent=IntentType.CATALOG_BROWSE,
                message="دي أهم الأقسام اللي عندنا. اختار قسم وانا أطلعلك أفضل كورسات." if is_ar else
                        "Here are our main catalog categories. Pick one and I’ll recommend the best courses.",
                categories=all_cats[:20],
                courses=[],
                errors=[],
                language="ar" if is_ar else "en",
                meta={"flow": "deterministic_catalog_browse"}
            )
            chat_res.session_id = session_id
            chat_res.request_id = request_id
            return JSONResponse(status_code=200, content=chat_res.model_dump(by_alias=True))

        # --- LLM-FREE FAST PATH: PAGINATION / MORE ---
        cached_ids = session_state.get("all_relevant_course_ids", [])
        pagination_offset = session_state.get("pagination_offset", 0)

        is_follow_up_intent = intent_result.intent == IntentType.FOLLOW_UP
        is_implicit_more = any(t in (request.message or "").lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])

        if (is_follow_up_intent or is_implicit_more) and cached_ids:
            logger.info(f"[{request_id}] Production Fast-Path: Serving cached results for Follow-Up.")

            new_offset = pagination_offset + 5
            if new_offset >= len(cached_ids):
                new_offset = 0

            state_updates = {"pagination_offset": new_offset}
            next_batch_ids = cached_ids[new_offset: new_offset + 5]
            courses = [retriever.get_course_details(cid) for cid in next_batch_ids if retriever.get_course_details(cid)]

            mock_semantic = SemanticResult(primary_domain="General", search_axes=[], is_in_catalog=True)
            mock_skills = SkillValidationResult(validated_skills=session_state.get("last_skills", []))

            chat_res = await response_builder.build(
                intent_result=intent_result,
                courses=courses,
                skill_result=mock_skills,
                user_message=request.message,
                context=session_state,
                semantic_result=mock_semantic
            )

            chat_res.session_id = session_id
            chat_res.request_id = request_id
            chat_res.meta = {
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "follow_up": True
            }

            if getattr(chat_res, "flow_state_updates", None):
                state_upd = chat_res.flow_state_updates.model_dump()
                state_upd.update(state_updates)
            else:
                state_upd = state_updates

            conversation_memory.add_assistant_message(
                session_id,
                chat_res.message,
                intent=IntentType.COURSE_SEARCH.value,
                state_updates=state_upd
            )
            return chat_res

        # Step 2: Semantic Layer
        previous_topic = session_state.get("last_role") or session_state.get("last_topic")

        if semantic_result_override:
            semantic_result = SemanticResult(**semantic_result_override, extracted_skills=[])
        else:
            if intent_result.intent == IntentType.GENERAL_QA:
                semantic_result = SemanticResult(primary_domain="General", is_in_catalog=True)
                logger.info(f"[{request_id}] Fast-Path: Skipped Semantic Layer for GENERAL_QA")
            else:
                semantic_result = await semantic_layer.analyze(
                    request.message,
                    intent_result,
                    previous_topic=previous_topic
                )

        # Honesty Guard
        honesty_guard_intents = [IntentType.COURSE_SEARCH, IntentType.COURSE_DETAILS, IntentType.LEARNING_PATH]
        if intent_result.intent in honesty_guard_intents and not semantic_result.is_in_catalog:
            logger.warning(f"[{request_id}] Honesty Guard Triggered: not in catalog -> SAFE_FALLBACK")
            intent_result.intent = IntentType.SAFE_FALLBACK
            intent_result.needs_courses = False

        # V6: Pagination & Context Persistence
        state_updates = {}
        is_more_request = any(t in (request.message or "").lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])
        cached_ids = session_state.get("all_relevant_course_ids", [])

        pagination_offset = session_state.get("pagination_offset", 0)
        if is_more_request:
            pagination_offset += 5
            state_updates["pagination_offset"] = pagination_offset
            logger.info(f"[{request_id}] 'More' request. Incremented offset to {pagination_offset}")

        can_use_cache = is_more_request and cached_ids and (intent_result.intent in [IntentType.COURSE_SEARCH, IntentType.CAREER_GUIDANCE])

        if can_use_cache:
            logger.info(f"[{request_id}] 'More' request detected. Using {len(cached_ids)} cached results.")
            courses = []
            for cid in cached_ids[pagination_offset:]:
                c = retriever.get_course_details(cid)
                if c:
                    courses.append(c)
            filtered_courses = courses
            skill_result = SkillValidationResult(validated_skills=session_state.get("last_skills", []))

        else:
            # IMPORTANT: remove non-existing intents from skip lists if you ever add them
            skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA]

            # If LEARNING_PATH and we have cached context
            if intent_result.intent == IntentType.LEARNING_PATH:
                if not intent_result.topic:
                    intent_result.topic = session_state.get("last_topic") or session_state.get("last_search_topic")
                    if intent_result.topic:
                        logger.info(f"[{request_id}] Context Recovery: Inferred topic '{intent_result.topic}' from session.")

                last_courses_ids = session_state.get("all_relevant_course_ids", [])
                if last_courses_ids and intent_result.topic:
                    filtered_courses = [retriever.get_course_details(cid) for cid in last_courses_ids[:5] if retriever.get_course_details(cid)]
                    filtered_courses = [c for c in filtered_courses if c]
                    skill_result = SkillValidationResult(validated_skills=[])
                    skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA, IntentType.LEARNING_PATH]
                else:
                    if intent_result.topic:
                        skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA]
                    else:
                        skip_search_intents = [IntentType.PROJECT_IDEAS, IntentType.GENERAL_QA, IntentType.LEARNING_PATH]

            if intent_result.intent in skip_search_intents:
                logger.info(f"[{request_id}] Skipping Course Search Pipeline for {_safe_intent_value(intent_result.intent)}")
                skill_result = SkillValidationResult(validated_skills=[])
                filtered_courses = []
                semantic_result = SemanticResult(primary_domain="General", is_in_catalog=True)
            else:
                logger.info(f"[{request_id}] Running Course Search Pipeline for {_safe_intent_value(intent_result.intent)}")
                skill_result, filtered_courses = await run_course_search_pipeline(
                    intent_result,
                    semantic_result,
                    request_id,
                    session_state,
                    is_more_request,
                    request.message
                )

            # Cache
            state_updates["all_relevant_course_ids"] = [c.course_id for c in filtered_courses]
            if not is_more_request:
                state_updates["pagination_offset"] = 0

                if intent_result.intent == IntentType.COURSE_SEARCH:
                    state_updates["last_topic"] = intent_result.topic or semantic_result.primary_domain
                    state_updates["last_role"] = intent_result.role
                    if semantic_result.user_level:
                        state_updates["last_level_preference"] = semantic_result.user_level
                    logger.info(f"[{request_id}] Persisted Context: Topic={state_updates.get('last_topic')} Level={state_updates.get('last_level_preference')}")

        # Step 6: Response Builder
        if semantic_result.brief_explanation:
            session_state["brief_explanation"] = semantic_result.brief_explanation

        chat_res = await response_builder.build(
            intent_result=intent_result,
            courses=filtered_courses,
            skill_result=skill_result,
            user_message=request.message,
            context=session_state,
            semantic_result=semantic_result
        )

        # Step 7: Metadata and Memory Update
        chat_res.session_id = session_id
        chat_res.request_id = request_id

        new_skills = skill_result.validated_skills
        if new_skills:
            state_updates["last_skills"] = new_skills
        if intent_result.role:
            state_updates["last_role"] = intent_result.role

        final_updates = state_updates.copy()
        if getattr(chat_res, "flow_state_updates", None):
            final_updates.update(chat_res.flow_state_updates.model_dump())

        # --- PATCH 5: Context Persistence ---
        session_state["last_intent"] = chat_res.intent.value if hasattr(chat_res.intent, "value") else str(chat_res.intent)
        if intent_result.topic:
            session_state["last_topic"] = intent_result.topic
        conversation_memory.update_session_state(session_id, session_state)

        conversation_memory.add_assistant_message(
            session_id,
            chat_res.message,
            intent=chat_res.intent,
            skills=new_skills,
            state_updates=final_updates
        )

        chat_res.meta = {
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "flow": "v2_full_pipeline"
        }

        return chat_res

    except Exception as e:
        logger.error(f"[{request_id}] Pipeline Error: {e}", exc_info=True)
        is_ar = _is_arabic_text(request.message)
        msg = "حصل خطأ داخلي بسيط. قولّي: مهتم بـ (Digital Marketing) ولا (Sales) ولا (Leadership)؟" if is_ar else \
              "A small internal error happened. Are you interested in Digital Marketing, Sales, or Leadership?"

        return ChatResponse(
            success=False,
            intent=IntentType.SAFE_FALLBACK,
            message=msg,
            courses=[],
            categories=["Programming", "Marketing", "Sales", "Leadership & Management"],
            errors=[f"{type(e).__name__}: {str(e)}"],
            language="ar" if is_ar else "en",
            meta={"flow": "error_handler"},
            session_id=session_id,
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
