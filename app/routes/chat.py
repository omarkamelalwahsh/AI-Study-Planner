"""
Chat endpoint - main RAG pipeline with 7-Step Career Guidance Flow.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ChatRequest, ChatResponse, ErrorResponse, CourseDetail, ChatSession, ChatMessage
import hashlib
import time
import uuid
import logging
from app.router import classify_intent, GroqUnavailableError
from app.retrieval import retrieve_courses, generate_search_plan, execute_and_group_search
from app.generator import generate_guidance_plan, generate_final_response
from app.skills import extract_skills_and_areas
from app.utils.normalization import normalize_text, wants_courses, detect_language

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/chat", response_model=ChatResponse, responses={503: {"model": ErrorResponse}})
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Main chat endpoint implementing 7-Step Pipeline.
    """
    start_time = time.time()
    
    try:
        # Step 0: Normalization
        raw_message = request.message
        message = normalize_text(raw_message)
        if not message or len(message) < 2:
            raise HTTPException(status_code=400, detail="Message too short")
        
        # Step 1: Session & Routing
        session_uuid = uuid.UUID(request.session_id) if request.session_id else uuid.uuid4()
        
        # Router
        try:
            router_out = classify_intent(message)
        except GroqUnavailableError:
             # Fallback
             from app.models import RouterOutput
             router_out = RouterOutput(in_scope=True, intent="SKILL_SEARCH", user_language="en")

        intent = router_out.intent
        logger.info(f"Session {session_uuid} | Intent: {intent}")

        # Pipeline Variables
        guidance_plan = {"guidance_intro": "", "core_areas": []}
        grounded_courses = []
        coverage_note = None
        
        # --- PATH A: CAREER GUIDANCE (The 7-Step Multi-Layer Flow) ---
        if intent == "CAREER_GUIDANCE":
            # Step 2: Guidance Planner (Stage 1)
            guidance_plan = generate_guidance_plan(message, router_out)
            
            # Step 3: Skill Extractor (Stage 2)
            skills_data = extract_skills_and_areas(message, guidance_plan.get("core_areas", []), router_out.target_role)
            
            # Step 4: Simple Search Plan (Deterministic)
            search_plan = {
                "plan": [
                    {
                        "canonical_en": s.get("canonical_en"),
                        "primary_queries": [s.get("canonical_en")] + (s.get("queries") if s.get("queries") else []),
                        "limit_per_query": 5
                    } for s in skills_data.get("skills_or_areas", [])
                ]
            }
            
            # Step 5 & 6: Execute Search
            # Use search_scope to decide if we filter by category (Hints only if search_scope is ALL_CATEGORIES)
            grounded_courses, skill_map = await execute_and_group_search(
                db, 
                search_plan, 
                target_categories=None if router_out.search_scope == "ALL_CATEGORIES" else router_out.target_categories
            )
            
            if not grounded_courses:
                coverage_note = "Our current catalog lacks direct matches for these specific skills."

        # --- PATH B: STANDARD SEARCH / OTHER ---
        else:
            # Traditional Retrieval (Layer 2 legacy style but using new Renderer)
            # We map "Standard Search" to "Guidance Plan" format so Renderer works.
            
            q = message
            if router_out.keywords:
                q = " ".join(router_out.keywords)
                
            # Execute standard retrieval
            offset = 0 # Simple pagination for now (always 0 for freshness in this refactor)
            filters = {}
            if router_out.target_categories:
                filters["category"] = router_out.target_categories[0] # Simplification
                
            raw_courses = await retrieve_courses(db, q, top_k=10, offset=offset, filters=filters)
            
            # Convert to dictionary format expected by formatted renderer
            dedup_map = {}
            for c in raw_courses:
                cid = str(c.course_id)
                if cid not in dedup_map:
                    cd = c.dict()
                    cd["supported_skills"] = ["Matched Query"] # Generic support
                    dedup_map[cid] = cd
                    
            grounded_courses = list(dedup_map.values())
            
            # Create a dummy guidance plan for the Renderer
            guidance_plan = {
                "guidance_intro": f"Here are the best results for your search: '{message}'",
                "core_areas": []
            }

        # Step 7: Final Renderer
        response_text = generate_final_response(
            user_question=message,
            guidance_plan=guidance_plan,
            grounded_courses=grounded_courses,
            language=router_out.user_language,
            coverage_note=coverage_note
        )
        
        # Logging & History (Simplified)
        latency_ms = int((time.time() - start_time) * 1000)
        
        try:
             # Check if session exists
            stmt = select(ChatSession).where(ChatSession.id == session_uuid)
            res = await db.execute(stmt)
            session = res.scalar_one_or_none()
            if not session:
                session = ChatSession(id=session_uuid, session_memory={})
                db.add(session)
            
            # Add messages
            db.add(ChatMessage(
                session_id=session_uuid, request_id=uuid.uuid4(), role="user", 
                content=message, intent=intent
            ))
            db.add(ChatMessage(
                session_id=session_uuid, request_id=uuid.uuid4(), role="assistant",
                content=response_text, intent=intent, retrieved_course_count=len(grounded_courses),
                latency_ms=latency_ms
            ))
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")

        # Convert grounded_courses back to schema for API response
        api_courses = []
        for c in grounded_courses:
            # c is a dict now
            api_courses.append(CourseDetail(
                course_id=str(c.get("course_id")),
                title=c.get("title"),
                level=c.get("level"),
                category=c.get("category"),
                instructor=c.get("instructor"),
                duration_hours=c.get("duration_hours"),
                description=c.get("description")[:200] if c.get("description") else None,
                skills=c.get("skills")[:100] if c.get("skills") else None,
                cover=c.get("cover")
            ))

        return ChatResponse(
            session_id=str(session_uuid),
            intent=intent,
            answer=response_text,
            courses=api_courses,
            request_id=str(uuid.uuid4())
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
