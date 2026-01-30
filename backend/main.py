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

        # Basic Text Extraction (Production requires robust OCR/Parser)
        try:
            if filename.endswith(".pdf"):
                try:
                    import pypdf
                    from io import BytesIO
                    reader = pypdf.PdfReader(BytesIO(content))
                    extracted_text = "\n".join([page.extract_text() for page in reader.pages])
                except ImportError:
                    logger.warning("pypdf not installed. Install via: pip install pypdf")
                    extracted_text = "PDF Parser unavailable. Please install pypdf."
                except Exception as pdf_err:
                     logger.warning(f"PDF parsing error: {pdf_err}")
                     extracted_text = "Error parsing PDF file."
                     
            elif filename.endswith(".docx"):
                try:
                    import docx
                    from io import BytesIO
                    doc = docx.Document(BytesIO(content))
                    extracted_text = "\n".join([para.text for para in doc.paragraphs])
                except ImportError:
                    logger.warning("python-docx not installed. Install via: pip install python-docx")
                    extracted_text = "Docx module unavailable. Please install python-docx."
                except Exception as docx_err:
                     logger.warning(f"DOCX parsing error: {docx_err}")
                     extracted_text = "Error parsing DOCX file."
            else:
                # Try decoding as text
                try:
                    extracted_text = content.decode("utf-8")
                except:
                    extracted_text = "Unsupported file format. Please upload PDF or DOCX."
        except Exception as e:
            logger.error(f"File reading error: {e}")
            extracted_text = "Error reading file content."

        if not extracted_text or not extracted_text.strip():
             extracted_text = "Empty CV or unreadable format."

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
        answer, projects, selected_courses, skill_groups, learning_plan, dashboard = await response_builder.build(
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
            projects=projects,
            skill_groups=skill_groups,
            learning_plan=learning_plan,
            dashboard=dashboard,
            error=None,
            request_id=request_id
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
        
        # V5/V6 NUCLEAR RULE: Context Persistence (Reuse intent/role for follow-ups)
        is_more_request = any(t in request.message.lower() for t in ["كمان", "غيرهم", "مزيد", "more", "next", "تانية"])
        
        # V5/V6 Persistence: Reuse intent for follow-ups or AMBIGUOUS role answers
        if (intent_result.intent in [IntentType.FOLLOW_UP, IntentType.AMBIGUOUS]) and session_state.get("last_intent"):
            last_intent_val = session_state.get("last_intent")
            if last_intent_val in [IntentType.LEARNING_PATH.value, IntentType.CAREER_GUIDANCE.value]:
                intent_result.intent = IntentType(last_intent_val)

        if intent_result.intent == IntentType.FOLLOW_UP or is_more_request:
             last_intent_val = session_state.get("last_intent")
             if last_intent_val:
                  logger.info(f"[{request_id}] Follow-up detected. Reusing intent: {last_intent_val}")
                  try:
                      if not intent_result.intent or intent_result.intent == IntentType.FOLLOW_UP:
                          intent_result.intent = IntentType(last_intent_val)
                  except ValueError:
                      pass
              
             if intent_result.role is None:
                  intent_result.role = session_state.get("last_role")
             if not getattr(intent_result, 'specific_course', None):
                  intent_result.specific_course = session_state.get("last_topic")

        logger.info(f"[{request_id}] Final Intent: {intent_result.intent.value}")
        
        # Step 2: Semantic Understanding
        # V5 Context Awareness: semantic layer needs to know the previous topic (role)
        previous_topic = session_state.get("last_role") or session_state.get("last_topic")
        
        semantic_result = await semantic_layer.analyze(
            request.message, 
            intent_result, 
            previous_topic=previous_topic
        )
        logger.info(f"[{request_id}] Skills extracted: {semantic_result.extracted_skills}")
        
        # V5: Inject Semantic Data (Explanation & Axes) into pipeline context
        if semantic_result.brief_explanation:
             intent_result.needs_explanation = True # Force explanation if semantic layer generated one
        
        # Attach search axes to intent_result for Relevance Guard
        # (Monkey-patching or using dynamic attribute since Pydantic model might need update if strict, 
        # but Python allows dynamic attrs implies we might need to update model definition if strictly typed.
        # Actually, let's update IntentResult model definition above if missed, 
        # but for now we can pass it via a separate arg to filter or attach to intent_result dynamic if Pydantic allows extra)
        # Better: We added `search_axes` to SemanticResult.
        # Let's pass `semantic_result.search_axes` to filter() explicitly or attach it.
        # Quick fix: Update IntentResult model in memory or pass as arg.
        # We will modify relevance_guard.filter signature in next step or attach to object.
        intent_result.search_axes = semantic_result.search_axes
             
        # Step 3: Skill & Role Extraction
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
        
        if session_state.get("last_skills"):
             logger.info(f"[{request_id}] Merging skills from Context: {session_state['last_skills']}")
             existing_skills = set(skill_result.validated_skills)
             for skill in session_state["last_skills"]:
                 if skill not in existing_skills:
                     skill_result.validated_skills.append(skill)
             
             # Also assume matching domain if possible
             if session_state.get("last_role") and "context_role" not in skill_result.skill_to_domain:
                  skill_result.skill_to_domain["context_role"] = session_state["last_role"]

        logger.info(f"[{request_id}] Validated skills: {skill_result.validated_skills}")
        
        # Step 4: Retrieval
        # V6: Context Bridge - If this is a follow-up for "more", ensure we use the previous topic
        search_topic = intent_result.specific_course or session_state.get("last_topic")
        
        courses = []
        filtered_courses = []

        # Strict RAG Layer Separation: Only retrieve if the intent explicitly needs courses
        needs_retrieval = intent_result.intent in [
            IntentType.COURSE_SEARCH, 
            IntentType.LEARNING_PATH, 
            IntentType.CAREER_GUIDANCE, # Needed for "How to become X" -> suggest courses
            IntentType.PROJECT_IDEAS,   # Needed if we want to suggest projects based on courses (optional)
            IntentType.CV_ANALYSIS,
            IntentType.COURSE_DETAILS,
            IntentType.FOLLOW_UP        # If follow up is course related
        ]
        
        # Override for FOLLOW_UP based on context
        if intent_result.intent == IntentType.FOLLOW_UP and not is_more_request:
             needs_retrieval = False # Just chat follow up

        if needs_retrieval:
            courses = retriever.retrieve(
                skill_result,
                level_filter=intent_result.level,
            )
            
            # If specific course query OR follow-up without results, search by title/topic
            if search_topic and (intent_result.specific_course or (is_more_request and not courses)):
                logger.info(f"[{request_id}] Searching courses by topic/title: {search_topic}")
                courses = retriever.retrieve_by_title(search_topic)
            
            # If still no courses and it's a follow-up, try with last_role
            if not courses and is_more_request and session_state.get("last_role"):
                logger.info(f"[{request_id}] Fallback search by last_role: {session_state.get('last_role')}")
                courses = retriever.retrieve_by_title(session_state.get("last_role"))
            
            # Enhance with semantic search if available and few results
            if semantic_search_enabled and len(courses) < 15:
                try:
                    from semantic_search import semantic_search
                    
                    # Production Fix: Query Expansion using Semantic Axes
                    if hasattr(intent_result, 'search_axes') and intent_result.search_axes:
                         search_query = " ".join(intent_result.search_axes)
                    else:
                         search_query = search_topic or request.message
                         
                    logger.info(f"[{request_id}] Semantic Retrieval: Using query: '{search_query}'")
                    semantic_results = semantic_search.search(search_query, top_k=15)
                    
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
            # Pass previous context to filter to avoid "is_more_request" filtering failures
            filtered_courses = relevance_guard.filter(
                courses,
                intent_result,
                skill_result,
                request.message,
                previous_domains=set(session_state.get("last_skills", []) + ([session_state.get("last_role")] if session_state.get("last_role") else []))
            )

            # V6: Pagination Logic - Filter out already shown courses for continuation requests
            last_shown_ids = session_state.get("last_results_course_ids", [])
            if is_more_request and last_shown_ids and (intent_result.intent in [IntentType.COURSE_SEARCH, IntentType.CAREER_GUIDANCE]):
                logger.info(f"[{request_id}] Filtering {len(last_shown_ids)} previously shown courses for pagination.")
                filtered_courses = [c for c in filtered_courses if c.course_id not in last_shown_ids]

        # If CATALOG_BROWSING, skip heavy retrieval and just get categories
        state_updates = {}
        if intent_result.intent == IntentType.CATALOG_BROWSING:
            all_categories = data_loader.get_all_categories()
            # We don't populate 'courses' or 'filtered_courses' to avoid hallucination in cards
            state_updates["available_categories"] = all_categories
            logger.info(f"[{request_id}] Catalog browsing: found {len(all_categories)} categories")
        
        # Step 6: Response Builder
        # Inject brief_explanation into session_state for the prompt
        if semantic_result.brief_explanation:
             session_state["brief_explanation"] = semantic_result.brief_explanation

        # Smart Fallback for Out-of-Scope queries
        if (intent_result.intent.value == "COURSE_SEARCH" 
            and not filtered_courses 
            and not intent_result.specific_course):
            
            topic = semantic_result.primary_domain or "Topic"
            logger.info(f"[{request_id}] Triggering Smart Fallback for topic: {topic}")
            answer, projects, selected_courses, skill_groups, learning_plan, dashboard = await response_builder.build_fallback(
                request.message,
                topic
            )
        else:
            answer, projects, selected_courses, skill_groups, learning_plan, dashboard = await response_builder.build(
                intent_result,
                filtered_courses,
                skill_result,
                request.message,
                context=session_state,
            )
        
        # Add roadmap for career guidance if available (Legacy fallback, V4 uses learning_plan)
        if intent_result.intent.value == "CAREER_GUIDANCE" and intent_result.role and not learning_plan:
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

        # Update session state with new shown course IDs (Pagination tracking)
        new_ids = [c.course_id for c in selected_courses]
        if is_more_request:
            # Append if we are scrolling
            combined_ids = list(dict.fromkeys(last_shown_ids + new_ids))
            state_updates["last_results_course_ids"] = combined_ids
        else:
            # Fresh search: Reset IDs
            state_updates["last_results_course_ids"] = new_ids

        # Store assistant response in memory
        conversation_memory.add_assistant_message(
            session_id,
            validated_answer,
            intent=intent_result.intent.value,
            role=intent_result.role,
            skills=skill_result.validated_skills,
            topic=semantic_result.primary_domain or intent_result.role or intent_result.specific_course,
            state_updates=state_updates
        )
        
        return ChatResponse(
            session_id=session_id,
            intent=intent_result.intent.value,
            answer=validated_answer,
            courses=display_courses,
            projects=projects,
            skill_groups=skill_groups,
            learning_plan=learning_plan,
            dashboard=dashboard,
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
