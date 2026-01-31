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

from config import API_HOST, API_PORT, LOG_LEVEL
from models import ChatRequest, ChatResponse, CourseDetail, ErrorDetail, IntentType, IntentResult
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

@app.get("/health")
async def health_check():
    """Requirement G: Production Health Check."""
    return {
        "status": "healthy",
        "data_loaded": data_loader.courses_df is not None,
        "retriever": retriever is not None,
        "memory": conversation_memory is not None
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
        answer, projects, selected_courses, skill_groups, learning_plan, dashboard, all_relevant, catalog_browsing, mode, f_question, refined_intent = await response_builder.build(
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
            mode=mode,
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
            followup_question=f_question
        )

    except Exception as e:
        logger.error(f"CV Upload failed: {e}", exc_info=True)
        return ChatResponse(
            session_id=session_id,
            intent="ERROR",
            answer="حدث خطأ أثناء تحليل السيرة الذاتية. تأكد أن الملف نصي (PDF/DOCX) وليس صورة ممسوحة ضوئياً.",
            courses=[],
            projects=[],
            error=ErrorDetail(code="UPLOAD_ERROR", message=str(e)),
            request_id=request_id
        )


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
        
        # Check if plan already asked in previous messages
        plan_asked = "تحب أعملك خطة زمنية" in context_str
        session_state["plan_asked"] = plan_asked
        
        # Step 1: Intent Router (with context)
        intent_result = await intent_router.classify(request.message, context_str)
        
        # --- CANONICALIZATION (Stop Drift) ---
        canonical = data_loader.canonicalize_query(request.message)
        if canonical:
            logger.info(f"[{request_id}] Canonical match: {canonical['primary_domain']}")
            intent_result.primary_domain = canonical.get("primary_domain")
            semantic_result_override = {
                "primary_domain": canonical.get("primary_domain"),
                "secondary_domains": canonical.get("secondary_domains", []),
                "focus_area": canonical.get("focus_area"),
                "tool": canonical.get("tool"),
                "semantic_lock": True
            }
        else:
            semantic_result_override = None

        # V5/V6 Persistence: Reuse intent for follow-ups or AMBIGUOUS role answers
        is_more_request = any(t in request.message.lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])
        
        if (intent_result.intent in [IntentType.FOLLOW_UP, IntentType.AMBIGUOUS]) and session_state.get("last_intent"):
            last_intent_val = session_state.get("last_intent")
            intent_result.intent = IntentType(last_intent_val)

        if intent_result.intent == IntentType.FOLLOW_UP or is_more_request:
             last_intent_val = session_state.get("last_intent")
             if last_intent_val:
                  logger.info(f"[{request_id}] Follow-up detected. Reusing intent: {last_intent_val}")
                  intent_result.intent = IntentType(last_intent_val)
              
             if intent_result.role is None:
                  intent_result.role = session_state.get("last_role")
             if not getattr(intent_result, 'specific_course', None):
                  intent_result.specific_course = session_state.get("last_topic")

        logger.info(f"[{request_id}] Final Intent: {intent_result.intent.value}")

        # --- REQUIREMENT B: TOPIC RESET POLICY (Stop Leakage) ---
        # Compute topic_key DETERMINISTICALLY
        def compute_topic_key(intent_r, msg: str) -> str:
            """Rule-based topic key computation for deterministic reset."""
            m = msg.lower()
            # Prefer canonical match
            canon = (intent_r.slots or {}).get("canonical")
            if canon:
                return canon.upper().replace(" ", "_")
            # Rule-based fallback
            if "فرونت" in m or "frontend" in m:
                return "FRONTEND_DEV"
            if "باك" in m or "backend" in m:
                return "BACKEND_DEV"
            if "hr" in m or "موارد بشرية" in m:
                return "HR"
            if "مدير" in m and ("مبرمج" in m or "ذكاء" in m or "ai" in m or "engineering" in m):
                return "ENG_MGMT"
            if "مبيعات" in m or "sales" in m:
                return "SALES"
            if intent_r.role:
                return intent_r.role.upper().replace(" ", "_")
            if intent_r.topic:
                return intent_r.topic.upper().replace(" ", "_")
            return "GENERAL"
        
        is_more = any(t in request.message.lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي", "results", "التالي"])
        new_topic_key = compute_topic_key(intent_result, request.message)
        old_topic_key = session_state.get("topic_key", "")
        
        if old_topic_key and new_topic_key != old_topic_key and not is_more:
            logger.info(f"[{request_id}] HARD RESET: Topic Switch ({old_topic_key} -> {new_topic_key})")
            session_state.update({
                "topic_key": new_topic_key,
                "pagination_offset": 0,
                "all_relevant_course_ids": [],
                "last_results_course_ids": [],
                "last_topic": None,
                "last_role": None,
                "last_skills": [],
            })
        else:
            session_state["topic_key"] = new_topic_key

        # --- V18 FIX 1: EXPLORATION (3 Guided Questions) ---
        if intent_result.intent == IntentType.EXPLORATION:
            answer = """
أهلاً! 👋 عشان أساعدك صح، محتاج أفهم شوية حاجات:

1️⃣ **خلفيتك إيه؟** (طالب / خريج جديد / عندك خبرة)
2️⃣ **تحب تشتغل في إيه أكتر؟** (Technology / Business / Design / أي حاجة)
3️⃣ **عندك وقت قد إيه للتعلم؟** (أسبوع / شهر / أكتر)

رد عليا بالـ 3 نقاط دول وأنا هرشحلك أحسن مسار! 🚀
"""
            # Add to memory
            conversation_memory.add_assistant_message(
                session_id, answer, 
                intent=intent_result.intent.value, 
                state_updates={"last_intent": "EXPLORATION", "exploration_mode": True}
            )
            
            return ChatResponse(
                session_id=session_id,
                intent=intent_result.intent,
                mode="exploration_questions",
                answer=answer,
                confidence=1.0,
                courses=[],
                projects=[],
                skill_groups=[],
                followup_question="مستني إجابتك!"
            )

        # --- HARD EXIT: CATALOG_BROWSING = DATA-ONLY (NO LLM, NO SEMANTIC) ---
        if intent_result.intent == IntentType.CATALOG_BROWSING:
            cats = sorted(data_loader.get_all_categories())
            bullets = "\n• " + "\n• ".join(cats)
            answer = f"تقدر تكتشف مجالات كتير عندنا! دي كل الأقسام المتاحة في الكتالوج:{bullets}\n\nاختار اسم قسم وأنا أطلعلك كورساته."
            
            state_updates = {
                "last_intent": IntentType.CATALOG_BROWSING.value,
                "topic_key": "CATALOG",
                "pagination_offset": 0,
                "all_relevant_course_ids": [],
                "last_results_course_ids": [],
                "last_topic": None,
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
                mode="category_explorer",
                answer=answer,
                confidence=1.0,
                courses=[],
                projects=[],
                skill_groups=[],
                catalog_browsing=CatalogBrowsingData(categories=cat_details, next_question="تختار أي قسم؟"),
                learning_plan=None,
                dashboard=None,
                error=None,
                request_id=request_id,
                followup_question="تحب تختار قسم منهم ولا تحب أساعدك تختار على حسب هدفك؟"
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
                # Skip the disambiguation block below by marking we have a specific topic
                # (intent_result now has specific_course set)

        # --- DETERMINISTIC FAST PATH: Broad Topic Disambiguation ---
        # Only for very short queries that are likely category searches (<= 4 words)
        # V12: DO NOT intercept CAREER_GUIDANCE here. Users want reasoning for guidance.
        # V17: Skip if user just selected a category (disambiguation resolved)
        if (len(request.message.split()) <= 4 
            and intent_result.intent in [IntentType.COURSE_SEARCH, IntentType.CATALOG_BROWSING]
            and not intent_result.specific_course):  # V17: Don't re-prompt if already resolved
            from models import CatalogBrowsingData, CategoryDetail
            suggested = data_loader.suggest_categories_for_topic(request.message)
            if suggested:
                answer = f"تمام - موضوع *{request.message}* واسع شوية. أقرب أقسام عندنا للموضوع ده:\n\n"
                answer += "\n".join([f"• {c}" for c in suggested])
                answer += "\n\nقولّي تختار أنهي قسم؟ وأنا أطلعلك كل الكورسات بتاعته."
                
                # V17: Store offered categories for disambiguation resolution
                state_updates = {
                    "last_intent": intent_result.intent.value, 
                    "last_topic": request.message, 
                    "pagination_offset": 0,
                    "offered_categories": suggested  # V17 RULE 3
                }
                conversation_memory.add_assistant_message(session_id, answer, intent=intent_result.intent.value, topic=request.message, state_updates=state_updates)
                
                return ChatResponse(
                    session_id=session_id,
                    intent=intent_result.intent,
                    mode="category_choice",
                    answer=answer,
                    confidence=intent_result.confidence or 0.99,
                    topic=request.message,
                    courses=[],
                    all_relevant_courses=[],
                    projects=[],
                    skill_groups=[],
                    catalog_browsing=CatalogBrowsingData(
                        categories=[CategoryDetail(name=c, why="استكشاف القسم") for c in suggested],
                        next_question="تختار أنهي قسم؟"
                    ),
                    request_id=request_id,
                    followup_question="تختار أنهي قسم؟"
                )

        # --- LLM-FREE FAST PATH: PAGINATION / MORE (V13/V15) ---
        cached_ids = session_state.get("all_relevant_course_ids", [])
        pagination_offset = session_state.get("pagination_offset", 0)

        if is_more and cached_ids and len(cached_ids) > pagination_offset + 3:
            logger.info(f"[{request_id}] Production Fast-Path: Serving cached results for 'More' request.")
            new_offset = pagination_offset + 3 # Batch of 3
            state_updates = {"pagination_offset": new_offset}
            next_batch_ids = cached_ids[new_offset : new_offset + 3]
            
            if not next_batch_ids: # Loop back
                 next_batch_ids = cached_ids[:3]
                 new_offset = 0
                 state_updates["pagination_offset"] = 0

            courses = [retriever.get_course_details(cid) for cid in next_batch_ids if retriever.get_course_details(cid)]
            
            from models import SemanticResult, SkillValidationResult
            mock_semantic = SemanticResult(primary_domain=new_topic_key, search_axes=[])
            mock_skills = SkillValidationResult(validated_skills=session_state.get("last_skills", []))
            
            answer, projects, selected, skills, plan, dash, all_rel, cat_b, mode, f_q, ref_intent = await response_builder.build(
                intent_result=intent_result,
                courses=courses,
                skill_result=mock_skills,
                user_message=request.message,
                context=session_state,
                semantic_result=mock_semantic
            )
            
            conversation_memory.add_assistant_message(session_id, answer, intent=intent_result.intent.value, state_updates=state_updates)
            return ChatResponse(
                session_id=session_id,
                intent=intent_result.intent,
                answer=answer,
                courses=selected,
                all_relevant_courses=all_rel,
                skill_groups=skills,
                mode="courses_only",
                request_id=request_id,
                followup_question=f_q
            )

        # Step 2: Semantic Layer (Deep Understanding)
        previous_topic = session_state.get("last_role") or session_state.get("last_topic")
        
        if semantic_result_override:
            from models import SemanticResult
            semantic_result = SemanticResult(**semantic_result_override, extracted_skills=[])
        else:
            semantic_result = await semantic_layer.analyze(
                request.message, 
                intent_result, 
                previous_topic=previous_topic
            )
        
        # Attach semantic data to intent result for pipeline grounding
        intent_result.primary_domain = semantic_result.primary_domain
        intent_result.search_axes = list(semantic_result.search_axes) if semantic_result.search_axes else []
             
        # Step 3: Skill & Role Extraction
        skill_result = skill_extractor.validate_and_filter(semantic_result)

        # --- SEED SKILL INJECTION (Anti-Empty V3) ---
        if not skill_result.validated_skills and intent_result.primary_domain == "Backend Development":
            # Priority: Databases, API, Language basics
            backend_seeds = ["sql", "databases", "api", "php", "web development", "javascript"]
            for s in backend_seeds:
                norm = data_loader.validate_skill(s)
                if norm and norm not in skill_result.validated_skills:
                    skill_result.validated_skills.append(norm)
            logger.info(f"[{request_id}] Injected backend seed skills: {skill_result.validated_skills}")

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
        
        # V7: Intelligent Skill Merging (Anti-Stickiness)
        # Only merge skills if we are in a 'More' request or a short confirmation
        is_more_request = any(t in request.message.lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية", "تاني", "باقي"])
        is_short_confirm = (request.message.strip().lower() in ["ياريت", "تمام", "ماشي", "ok", "yes", "confirm", "وافقت", "أيوه", "ايوه"])

        should_merge_context = (is_more_request or is_short_confirm) and not intent_result.role
        
        if session_state.get("last_skills") and should_merge_context:
             logger.info(f"[{request_id}] Merging skills from Context: {session_state['last_skills']}")
             existing_skills = set(skill_result.validated_skills)
             for skill in session_state["last_skills"]:
                 if skill not in existing_skills:
                     skill_result.validated_skills.append(skill)
             
             if session_state.get("last_role") and "context_role" not in skill_result.skill_to_domain:
                  skill_result.skill_to_domain["context_role"] = session_state["last_role"]
        
        # Merged Intent: Skip strict axes filtering for roadmaps
        guidance_intents = [IntentType.LEARNING_PATH, IntentType.CAREER_GUIDANCE]
        
        logger.info(f"[{request_id}] Validated skills: {skill_result.validated_skills}")
        
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
        else:
            # Step 4: Retrieval
            # V6: Context Bridge - If this is a follow-up for "more" but no cache, or new search
            search_topic = intent_result.specific_course or session_state.get("last_topic")
            
            courses = []
            filtered_courses = []

            # Reset offset for NEW search
            if not is_more_request:
                state_updates["pagination_offset"] = 0
                pagination_offset = 0

            # Strict RAG Layer Separation: Only retrieve if the intent explicitly needs courses
            needs_retrieval = intent_result.intent in [
                IntentType.COURSE_SEARCH, 
                IntentType.LEARNING_PATH, 
                IntentType.CAREER_GUIDANCE, 
                IntentType.PROJECT_IDEAS,
                IntentType.CV_ANALYSIS,
                IntentType.COURSE_DETAILS,
                IntentType.FOLLOW_UP,
                IntentType.GENERAL_QA
            ]
            
            if needs_retrieval:
                courses = retriever.retrieve(
                    skill_result,
                    level_filter=intent_result.level,
                    focus_area=semantic_result.focus_area,
                    tool=semantic_result.tool,
                )
                
                if search_topic and (intent_result.specific_course or (is_more_request and not courses)):
                    logger.info(f"[{request_id}] Searching courses by topic/title: {search_topic}")
                    courses = retriever.retrieve_by_title(search_topic)
                
                if not courses and is_more_request and session_state.get("last_role"):
                    logger.info(f"[{request_id}] Fallback search by last_role: {session_state.get('last_role')}")
                    courses = retriever.retrieve_by_title(session_state.get("last_role"))
                
                if semantic_search_enabled and len(courses) < 15:
                    try:
                        # V16: Use topic_key to prevent semantic query contamination
                        msg_str = str(request.message or "").lower()
                        is_generic = len(msg_str.split()) < 4 and any(t in msg_str for t in ["courses", "find", "there", "show", "any"])
                        
                        # Ensure search_axes is iterable
                        axes = getattr(intent_result, 'search_axes', []) or []
                        search_axes_str = " ".join([str(a) for a in axes if a])
                        
                        # V16 FIX: Use topic_key for deterministic query selection
                        topic_key = session_state.get("topic_key", "")
                        if topic_key and topic_key not in ["GENERAL", "CATALOG"]:
                            search_query = topic_key.replace("_", " ")
                        elif is_generic and search_axes_str:
                             search_query = search_axes_str
                        else:
                             search_query = search_axes_str if search_axes_str else (search_topic or request.message)
                        
                        if not search_query:
                             search_query = "courses" # Absolute fallback
                             
                        logger.info(f"[{request_id}] Semantic Retrieval: Using query: '{search_query}'")
                        semantic_results = semantic_search.search(search_query, top_k=20)
                        seen_ids = {c.course_id for c in courses}
                        for course_id, score in semantic_results:
                            if course_id not in seen_ids:
                                course = retriever.get_course_details(course_id)
                                if course:
                                    courses.append(course)
                                    seen_ids.add(course_id)
                    except Exception as e:
                        logger.warning(f"Semantic search fallback failed: {e}")
                
                logger.info(f"[{request_id}] Retrieved {len(courses)} raw courses")
                
                # Step 5: Relevance Guard
                filtered_courses = relevance_guard.filter(
                    courses,
                    intent_result,
                    skill_result,
                    request.message,
                    previous_domains=set(session_state.get("last_skills", []) + ([session_state.get("last_role")] if session_state.get("last_role") else [])),
                    semantic_result=semantic_result
                )

                # Cache THE FULL LIST for pagination (V13 Production Standard)
                state_updates["all_relevant_course_ids"] = [c.course_id for c in filtered_courses]
                state_updates["pagination_offset"] = 0 # Reset for new search

        # Step 6: Response Builder
        if semantic_result.brief_explanation:
             session_state["brief_explanation"] = semantic_result.brief_explanation
        
        # Pass categories for discovery
        available_categories = data_loader.get_all_categories()

        # Context fix: user confirmations
        short_confirmations = ["ياريت", "تمام", "ماشي", "ok", "yes", "confirm", "وافقت", "أيوه", "ايوه"]
        if request.message.strip().lower() in short_confirmations:
            session_state["is_short_confirmation"] = True
            session_state["last_followup"] = session_state.get("last_followup_question")

        # Smart Fallback for Out-of-Scope queries
        all_relevant = []
        if (intent_result.intent.value == "COURSE_SEARCH" and not filtered_courses and not intent_result.specific_course):
            answer, projects, selected_courses, skill_groups, learning_plan, dashboard, all_relevant, catalog_browsing, mode, f_question, refined_intent = await response_builder.build_fallback(
                request.message,
                semantic_result.primary_domain or "Topic"
            )
        else:
            answer, projects, selected_courses, skill_groups, learning_plan, dashboard, all_relevant, catalog_browsing, mode, f_question, refined_intent = await response_builder.build(
                intent_result=intent_result,
                courses=filtered_courses,
                skill_result=skill_result,
                user_message=request.message,
                context=session_state,
                available_categories=available_categories,
                semantic_result=semantic_result
            )
        
        # Step 7: Consistency Check
        validated_answer, v_courses = consistency_checker.final_check(answer, selected_courses)
        
        # New: Consistency check for all_relevant
        _, v_all_relevant = consistency_checker.final_check("", all_relevant)
        
        # Limit courses for response (display limit)
        display_courses = relevance_guard.limit_results(v_courses, max_courses=10)
        
        # Update session state with new shown course IDs (Pagination tracking)
        # In V10, we store ALL relevant IDs for future "more" requests if needed
        all_ids = [c.course_id for c in v_all_relevant]
        state_updates["all_relevant_course_ids"] = all_ids
        
        shown_ids = [c.course_id for c in v_courses]
        state_updates["last_results_course_ids"] = shown_ids
        
        # Consistent intent value (Refined by LLM if possible)
        final_intent_str = refined_intent or intent_result.intent.value

        # --- NUCLEAR SHIELD: Final UI Safety Checks ---
        validated_answer = validated_answer or answer or "إليك ما وجدته في كتالوج الكورسات المتاح لدينا."
        f_question = f_question or "هل تود التوسع في نقطة معينة؟"
        v_courses = v_courses or []
        v_all_relevant = v_all_relevant or []
        projects = projects or []
        skill_groups = skill_groups or []

        # Store assistant response in memory (with all state updates)
        state_updates["last_followup_question"] = f_question or getattr(response_builder, 'last_followup_question', "") or ""

        # --- SMART FOLLOW-UP: Backend Stack Discovery ---
        final_followup = f_question
        if intent_result.primary_domain == "Backend Development":
            stack_keywords = ["python", "django", "flask", "php", "laravel", "node", "express", "java", "spring", ".net", "c#", "ruby"]
            if not any(kw in request.message.lower() for kw in stack_keywords):
                if not is_more_request and not is_short_confirm:
                    final_followup = "تحب تبدأ مسار الـ Backend بـ Python ولا PHP ولا Node.js؟"
                    state_updates["last_followup_question"] = final_followup

        conversation_memory.add_assistant_message(
            session_id,
            validated_answer,
            intent=final_intent_str,
            role=intent_result.role,
            skills=skill_result.validated_skills,
            # V10 Fix: Ensure GENERAL_QA subject is stored as topic
            topic=semantic_result.primary_domain or intent_result.role or intent_result.specific_course,
            state_updates=state_updates
        )
        
        # --- FINAL UI SAFETY SHIELD (Requirement C) ---
        response_payload = {
            "session_id": session_id,
            "intent": IntentType(final_intent_str),
            "mode": mode, 
            "answer": validated_answer,
            "confidence": intent_result.confidence or 0.5,
            "topic": intent_result.specific_course or intent_result.role or semantic_result.primary_domain,
            "role": intent_result.role,
            "courses": display_courses[:5] if display_courses else [], 
            "all_relevant_courses": v_all_relevant or [],
            "projects": projects or [],
            "skill_groups": skill_groups or [],
            "catalog_browsing": catalog_browsing,
            "learning_plan": learning_plan,
            "dashboard": dashboard,
            "request_id": request_id,
            "followup_question": final_followup
        }

        try:
            return ChatResponse.model_validate(response_payload)
        except Exception as eval_err:
            logger.error(f"[{request_id}] Schema Validation Failed: {eval_err}")
            # Degrade gracefully to a minimal valid response
            return ChatResponse(
                session_id=session_id,
                intent=IntentType.ERROR,
                answer="عذراً حدث خطأ في معالجة البيانات، جاري الإصلاح." if data_loader.is_arabic(request.message) else "Sorry, a data validation error occurred.",
                request_id=request_id
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
