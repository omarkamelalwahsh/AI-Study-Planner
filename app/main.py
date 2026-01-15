from typing import List, Dict, Any, Optional
import uuid
import os
import logging
import json
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from dotenv import load_dotenv

from app.db import get_db, SessionLocal, engine
from app.models import SearchQuery, Plan, PlanWeek, PlanItem, Course, ChatSession, ChatMessage, UserMemory, SavedPlan
from app.search.retrieval import SearchEngine
from app.schemas import PlanGenerateRequest
from app.services.plan_service import create_plan
from app.search.embedding import normalize_ar, expand_query

from app.core.config import settings
from app.schemas_career import CareerCopilotRequest, PlanOutput, ErrorResponse, ErrorDetail
from app.services.career_copilot.intent_router import IntentRouter
from app.services.career_copilot.role_advisor import RoleAdvisor
from app.services.career_copilot.course_recommender import CourseRecommender
from app.services.career_copilot.study_planner import StudyPlanner
from app.services.career_copilot.response_composer import ResponseComposer
from app.services.career_copilot.assessment_service import AssessmentService
from app.middleware.structured_logging import StructuredLoggingMiddleware
from app.export.pdf_exporter import PDFExporter

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("app")

app = FastAPI(title="AI Study Planner")
app.add_middleware(StructuredLoggingMiddleware)

# Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

DATA_DIR = settings.DATA_DIR

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled 500: {exc}")
    if request.url.path.startswith("/api/") or "json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": False, "error": "Internal Server Error"}, status_code=500)
    return templates.TemplateResponse("error.html", {
        "request": request,
        "detail": str(exc) if settings.APP_ENV == "dev" else "حدث خطأ غير متوقع في الخادم."
    }, status_code=500)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or "json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": False, "error": exc.detail}, status_code=exc.status_code)
    return templates.TemplateResponse("error.html", {
        "request": request,
        "detail": exc.detail
    }, status_code=exc.status_code)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Career Copilot...")
    
    # 0. Create tables if they don't exist
    from app.models import Base
    from app.db import engine
    Base.metadata.create_all(bind=engine)
    
    # 1. Validate index files exist
    index_files = ["faiss.index", "course_embeddings.npy", "index_meta.json"]
    for f in index_files:
        path = os.path.join(DATA_DIR, f)
        if not os.path.exists(path):
            logger.warning(f"Index missing: {f}. Retrieval might be degraded.")
            # We don't raise RuntimeError here to allow the app to start and show a nice error page if needed
            # or allow the user to trigger a rebuild from a future admin UI.
    
    # 2. Check meta
    meta_path = os.path.join(DATA_DIR, "index_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        logger.info(f"Index Meta: model={meta.get('model_name')}, count={meta.get('count')}, dim={meta.get('dim')}")
    
    # 3. Connect to DB and verify courses
    db = SessionLocal()
    try:
        count = db.query(Course).count()
        if count == 0:
            logger.warning("DB is empty. No courses found.")
        else:
            logger.info(f"DB connected. Found {count} courses.")
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
    finally:
        db.close()
    
    # Load index into memory
    try:
        SearchEngine.load_index()
    except Exception as e:
        logger.error(f"Failed to load search index: {e}")
    
    logger.info("Startup complete.")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "query_text": "",
        "top_k": 5,
        "weeks": 4,
        "hours_per_week": 10
    })

@app.post("/search", response_class=HTMLResponse)
async def search_endpoint(
    request: Request,
    query_text: str = Form(...),
    weeks: int = Form(4),
    hours_per_week: float = Form(10),
    db: Session = Depends(get_db)
):
    # --- DIAGNOSTICS START ---
    # Requested by user: 3 numbers
    try:
        count = db.query(Course).count()
        levels = db.query(Course.level).distinct().all()
        distinct_levels = [l[0] for l in levels]
        
        SearchEngine.load_index()
        index_size = SearchEngine._index.ntotal if SearchEngine._index else -1
        
        logger.info(f"--- DIAGNOSTICS ---")
        logger.info(f"1. Courses in DB: {count}")
        logger.info(f"2. Distinct Levels: {distinct_levels}")
        logger.info(f"3. Index Size: {index_size}")
        logger.info(f"-------------------")
    except Exception as e:
        logger.error(f"Diagnostics failed: {e}")
    # --- DIAGNOSTICS END ---

    normalized_query = normalize_ar(query_text)
    expanded = expand_query(normalized_query)
    
    # Log query
    sq = SearchQuery(raw_query=query_text, normalized_query=normalized_query)
    db.add(sq)
    db.commit()
    db.refresh(sq)
    
    # 1. Use Strict Search Router
    from app.search.router import SearchRouter
    search_response = SearchRouter.route_query(query_text)
    
    logger.info(
        f"Search: '{query_text}' -> "
        f"Route: {search_response.get('route', 'unknown')} | "
        f"Status: {search_response.get('status', 'unknown')}"
    )
    # Flatten results for Plan Generation
    results = []
    results_by_level = search_response.get("results_by_level", {})
    for lvl_results in results_by_level.values():
        results.extend(lvl_results)
    
    total_found = len(results)
    
    # 3. Generate plan automatically (Only if we have results)
    plan = None
    if total_found > 0:
        try:
            plan_id = create_plan(query_text, sq.id, weeks, hours_per_week, results)
            logger.info(f"Plan created: {plan_id} with {len(results)} courses")
            
            # Fetch created plan with relationships
            plan = db.query(Plan).options(
                joinedload(Plan.weeks_obj).joinedload(PlanWeek.items).joinedload(PlanItem.course)
            ).filter(Plan.id == plan_id).first()
            
            # Sort weeks and items
            if plan:
                plan.weeks_obj.sort(key=lambda w: w.week_number)
                for w in plan.weeks_obj:
                    w.items.sort(key=lambda i: i.order_in_week)
        except Exception as e:
            logger.exception("Plan generation failed")
            # Continue anyway to show search results
    
    # Determine "selected_level" for UI highlight
    # logic: if level_filtered, find which key has data? 
    # Or just pass None if all_levels.
    selected_level = None
    if search_response["level_mode"] == "level_filtered":
        # Find the level key
        for k in results_by_level:
             selected_level = k
             break

    return templates.TemplateResponse("unified_results.html", {
        "request": request,
        "search_mode": search_response["level_mode"], # maps to old 'mode'
        "selected_level": selected_level,
        "courses_grouped": results_by_level,
        "search_message": search_response.get("message", "No results found"), # New UI field
        "router_status": search_response.get("status", "unknown"),   # New UI field
        "plan": plan,
        "query_id": sq.id,
        "query_text": query_text,
        "normalized_query": normalized_query,
        "total_found": total_found,
        "weeks": weeks,
        "hours_per_week": hours_per_week
    })

@app.get("/course/{course_id}", response_class=HTMLResponse)
async def course_detail(request: Request, course_id: str, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return templates.TemplateResponse("course_detail.html", {
        "request": request,
        "course": course
    })

@app.post("/plan/generate")
async def generate_plan_endpoint(req: PlanGenerateRequest, db: Session = Depends(get_db)):
    logger.info(f"Generating plan for query_id={req.query_id}, weeks={req.weeks}, hours={req.hours_per_week}")
    
    q_text = req.query_text
    if not q_text and req.query_id:
        sq = db.query(SearchQuery).filter(SearchQuery.id == req.query_id).first()
        if sq:
            q_text = sq.raw_query
    
    if not q_text:
        return JSONResponse({"ok": False, "error": "No query text provided"}, status_code=400)
        
    try:
        # Re-run search Fresh Retrieval as required (need enough candidates for plan)
        candidates = SearchEngine.search(q_text)
        
        plan_id = create_plan(q_text, req.query_id, req.weeks, req.hours_per_week, candidates)
        logger.info(f"Plan created: {plan_id} with {len(candidates)} candidates")
        
        return JSONResponse({
            "ok": True, 
            "plan_id": plan_id, 
            "redirect_url": f"/plan/{plan_id}"
        })
    except Exception as e:
        logger.exception("Plan generation failed")
        detail = f"{type(e).__name__}: {e}" if os.getenv("APP_ENV") == "dev" else "Plan generation failed"
        return JSONResponse({"ok": False, "error": detail}, status_code=500)

@app.get("/plan/{plan_id}", response_class=HTMLResponse)
async def view_plan(request: Request, plan_id: str, db: Session = Depends(get_db)):
    plan = db.query(Plan).options(
        joinedload(Plan.weeks_obj).joinedload(PlanWeek.items).joinedload(PlanItem.course)
    ).filter(Plan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(404, "Plan not found")
        
    # Sort weeks and items
    plan.weeks_obj.sort(key=lambda w: w.week_number)
    for w in plan.weeks_obj:
        w.items.sort(key=lambda i: i.order_in_week)
    
    return templates.TemplateResponse("plan_view.html", {
        "request": request,
        "plan": plan
    })

@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, db: Session = Depends(get_db)):
    """Display all past plans ordered by creation date (newest first)"""
    plans = db.query(Plan).options(
        joinedload(Plan.weeks_obj).joinedload(PlanWeek.items),
        joinedload(Plan.query)
    ).order_by(Plan.created_at.desc()).all()
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "plans": plans
    })

@app.get("/debug/index")
async def debug_index():
    meta_path = os.path.join(DATA_DIR, "index_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            return json.load(f)
    return {"error": "Index not found"}


@app.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Production-grade readiness check: DB reachable + Indexes present"""
    try:
        db.execute(text("SELECT 1"))
        SearchEngine.load_index()
        if not SearchEngine._index:
             return JSONResponse({"status": "not_ready", "reason": "Search index not loaded"}, status_code=503)
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse({"status": "not_ready", "reason": str(e)}, status_code=503)

@app.get("/health")
async def health_check():
    """Simple process health check"""
    return {"status": "ok"}

# Career Copilot APIs

@app.post("/career-copilot", response_model=PlanOutput)
async def career_copilot_endpoint(req: CareerCopilotRequest, db: Session = Depends(get_db)):
    """
    Main entry point for production-grade Career Copilot.
    Pipeline: Language -> Intent -> Role Advisor -> Course Recommender -> Study Planner -> Response Composer
    """
    import uuid
    
    # 1. Session Management
    session_id = req.session_id
    if req.new_session or not session_id:
        session = ChatSession(title=f"Session {req.message[:20]}...")
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    
    # 2. Intent Analysis (Step 1 & 2)
    intent = IntentRouter.parse_intent(req.message)
    
    # 3. Role Knowledge Retrieval (Step 3)
    advisor = RoleAdvisor()
    role_info = advisor.get_role_info(intent.career_goal or "General", intent.sector)
    
    # 4. Course Recommendation (Step 4)
    recommended = CourseRecommender.recommend(role_info["required_skills"], req.constraints.dict())
    
    # 5. Study Planning (Step 5)
    plan_data = StudyPlanner.generate_plan(role_info["required_skills"], recommended, req.constraints.dict())
    
    # 6. Response Composition (Step 6)
    plan_output = ResponseComposer.compose(
        session_id=session_id,
        intent=intent,
        role_info=role_info,
        plan_data=plan_data,
        recommended_courses=recommended,
        lang_policy=req.constraints.preferred_language or intent.language
    )
    
    # 7. PDF Export (Step 9 - if requested)
    if req.export_pdf:
        pdf_path = PDFExporter.generate_pdf(plan_output)
        from app.schemas_career import PDFInfo
        plan_output.pdf = PDFInfo(pdf_id=str(uuid.uuid4()), pdf_url=f"/static/exports/{os.path.basename(pdf_path)}")
    
    # 8. Persistence (Persistence of history)
    msg_user = ChatMessage(session_id=session_id, role="user", content=req.message)
    msg_assistant = ChatMessage(
        session_id=session_id, 
        role="assistant", 
        content=plan_output.summary,
        intent_json=intent.dict(),
        plan_output_json=plan_output.dict()
    )
    db.add(msg_user)
    db.add(msg_assistant)
    db.commit()
    
    return plan_output

@app.post("/api/assessment/questions")
async def get_assessment_questions(field: str, level: str = "beginner"):
    return AssessmentService.get_assessment_questions(field, level)

@app.post("/api/assessment/evaluate")
async def evaluate_level(answers: Dict[str, str]):
    level = AssessmentService.evaluate_level(answers)
    return {"level": level}

@app.get("/api/sessions/{id}")
async def get_session(id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    return session

@app.get("/api/sessions/{id}/messages")
async def get_messages(id: uuid.UUID, limit: int = 50, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == id).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    return messages

@app.get("/api/memory")
async def list_memory(user_id: uuid.UUID, db: Session = Depends(get_db)):
    memory = db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
    return memory
