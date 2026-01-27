"""
Chat endpoint - main RAG pipeline with 7-Step Career Guidance Flow.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ChatRequest, ChatResponse, ErrorResponse, CourseDetail, ChatSession, ChatMessage
import hashlib
import time
import uuid
import logging
import re
from app.router import classify_intent, GroqUnavailableError
from app.retrieval import retrieve_courses, generate_search_plan, execute_and_group_search
from app.generator import (
    generate_guidance_plan, 
    generate_final_response, 
    generate_project_ideas,
    _relevance_gate
)
from app.skills import extract_skills_and_areas
from app.utils.normalization import normalize_text, wants_courses, detect_language
from app.followup_manager import FollowupManager, generate_dynamic_projects, update_session_context

logger = logging.getLogger(__name__)
router = APIRouter()

# Domain Blacklist to prevent cross-domain hallucinations (Ultra-Strict)
DOMAIN_BLACKLIST = {
    "technical": ["Graphic Design", "Digital Media", "Health & Wellness", "Banking Skills", "Customer Service", "Human Resources", "Leadership", "Sales", "Management", "General", "Project Management", "Personal Productivity", "General Office"],
    "design": ["Programming", "Hacking", "Data Security", "Networking", "Banking Skills", "Technology Applications", "Project Management", "Human Resources", "Sales", "Management"],
    "soft_skills": ["Programming", "Hacking", "Data Security", "Networking", "Web Development", "Mobile Development", "Data Analysis"]
}

def is_blacklisted(role_type: str, category: str) -> bool:
    # Soft Relevance Rule: We do NOT hard-block courses by category anymore.
    # The 'hard_skill_gate' below will handle relevance verification.
    return False

def hard_skill_gate(course: Dict, skills: List[str]) -> bool:
    """
    ULTRA-STRICT Rule: A course MUST have a strong semantic match with at least one extracted skill.
    Normalization is key to preventing leaks.
    """
    if not skills:
        return False
        
    title = str(course.get("title", "")).lower()
    category = str(course.get("category", "")).lower()
    description = str(course.get("description", "")).lower()
    course_skills = [s.lower() for s in (course.get("skills") or [])]
    
    # Combined target text for broad matching
    combined_text = f"{title} {category} {description}"
    
    # Clean up symbols for precision
    def clean(t): return re.sub(r"[^a-z0-9\s\+\#\.]", " ", t.lower())
    
    normalized_text = clean(combined_text)
    
    for s in skills:
        s_clean = clean(s).strip()
        if not s_clean: continue
        
        # 1. Exact match in course.skills (Highest Precision)
        if any(s_clean == cs for cs in course_skills):
            return True
            
        # 2. Substring match for short technical terms (SQL, PHP, C++, C#, JS)
        # Avoid matching 'is' or 'at' by enforcing word boundaries for short terms
        if len(s_clean) <= 3:
            pattern = rf"\b{re.escape(s_clean)}\b"
            if re.search(pattern, normalized_text):
                return True
        else:
            # For longer terms, simple inclusion is usually safe
            if s_clean in normalized_text:
                return True
                
    return False

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

        coverage_note = None
        
        # Step 1.5: Query Optimization for Data Analysis
        optimized_keywords = []
        if any(x in message.lower() for x in ["data", "تحليل", "بيانات"]):
            optimized_keywords = ["Excel", "SQL", "Python", "Data Analysis"]

        # Fetch Chat History for Context
        history_stmt = select(ChatMessage).where(ChatMessage.session_id == session_uuid).order_by(ChatMessage.created_at.desc()).limit(5)
        history_res = await db.execute(history_stmt)
        chat_history_objs = history_res.scalars().all()[::-1] # Order chronologically for LLM
        chat_history = [{"role": m.role, "content": m.content} for m in chat_history_objs]
        
# -----------------------
# Chat API
# -----------------------


# -----------------------
# Chat API
# -----------------------
        # STEP 0: FOLLOW-UP MANAGER (Bypass Retrieval?)
        # -----------------------------
        if FollowupManager.should_rerun_retrieval(message, str(session_uuid)) is False:
             # Logic: It IS a follow-up ("more projects") AND we have context.
             # 1. Infer Level (e.g. "Harder", "Easier")
            requested_level = FollowupManager.infer_requested_level(message)
            
            # 2. Dynamic Project Generation (No RAG needed)
            new_projects = generate_dynamic_projects(str(session_uuid), requested_level)
            
            # Construct a simple direct response
            return ChatResponse(
                session_id=str(session_uuid),
                intent="FOLLOW_UP",
                answer="Here are some additional project ideas for you:",
                skills=[],
                primary_courses=[], # Explicitly empty as requested
                secondary_courses=[],
                projects=new_projects,
                request_id=str(uuid.uuid4())
            )
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
                        "primary_queries": [s.get("canonical_en")] + s.get("primary_queries", []) + s.get("fallback_queries", []),
                        "limit_per_query": 10
                    } for s in skills_data.get("skills_or_areas", [])
                ] + [
                    {
                        "canonical_en": kw,
                        "primary_queries": [kw],
                        "limit_per_query": 10
                    } for kw in optimized_keywords
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

        # --- PATH B: FOLLOW-UP FALLBACK (Context Lost) ---
        elif intent == "FOLLOW_UP" or (FollowupManager.is_followup(message) and not grounded_courses):
            # We detected a follow-up intent ("More ideas") but 'should_rerun_retrieval' 
            # returned True (likely because context.last_topic was None).
            # OR we fell through standard search with no results but it looked like a "more" request.
            # Instead of searching for "more", we ask for clarification.
            return ChatResponse(
                session_id=str(session_uuid),
                intent=intent,
                answer="I'd love to help with more ideas! Could you remind me which topic or role you're focusing on? (e.g., 'More Python projects' or 'More Marketing ideas')",
                skills=[],
                courses=[],
                projects=[],
                request_id=str(uuid.uuid4())
            )

        # --- PATH C: STANDARD SEARCH / OTHER ---
        else:
            is_yes = any(x in message.lower() for x in ["ايوه", "أيوة", "نعم", "طبعا", "yes", "sure", "ok"])
            is_no = any(x in message.lower() for x in ["لأ", "لا", "شكرا", "no", "thanks"])
            
            # Execute search ONLY if not a simple yes/no
            if not (is_yes or is_no):
                search_queries = [message]
                if router_out.keywords:
                    search_queries = router_out.keywords + search_queries
                    
                dedup_map = {}
                for sq in search_queries[:6]:
                    raw_courses = await retrieve_courses(db, sq, top_k=20, filters=None)
                    for c in raw_courses:
                        cid = str(c.course_id)
                        if cid not in dedup_map:
                            cd = c.dict()
                            cd["supported_skills"] = ["Search Match"]
                            dedup_map[cid] = cd
                grounded_courses = list(dedup_map.values())
            
            # Create a dummy guidance plan for the Renderer
            guidance_plan = {
                "guidance_intro": f"Results for: {message}",
                "core_areas": []
            }

        # --- UNIVERSAL FALLBACK MECHANISM (Stage 3: Context-Aware Retrieval) ---
        # If after initial search, we still have NO CARDS, we try a desperate contextual search.
        if not grounded_courses and intent in ["CAREER_GUIDANCE", "SKILL_SEARCH", "SEARCH"]:
            logger.info(f"Session {session_uuid} | All primary matching failed. Triggering Context-Aware Fallback.")
            
            # 1. Determine Fallback Query (Highest priority: Target Role, Second: Keywords, Last: Original Question)
            fallback_candidates = []
            if router_out.target_role:
                fallback_candidates.append(router_out.target_role)
            if router_out.keywords:
                fallback_candidates.extend(router_out.keywords[:3])
            
            # 2. Retrieve broad results from ANY relevant context
            fallback_dedup = {}
            for fq in fallback_candidates[:5]:
                fallback_results = await retrieve_courses(db, query=fq, top_k=20, filters=None)
                for c in fallback_results:
                    cid = str(c.course_id)
                    if cid not in fallback_dedup:
                        fallback_dedup[cid] = c.dict()
            
            # 3. Apply Relevance Gate (Sanity check to avoid totally random noise)
            candidate_list = list(fallback_dedup.values())
            if candidate_list:
                # Use the target role or message as a gate context
                gate_context = router_out.target_role or message
                grounded_courses = _relevance_gate(gate_context, candidate_list)
                
                if grounded_courses:
                    # Mark these as primary so they show up as cards!
                    coverage_note = "Showing the closest matches found in our catalog for your role."
                    logger.info(f"Session {session_uuid} | Fallback found {len(grounded_courses)} contextual courses.")
                else:
                    coverage_note = "Our catalog currently lacks exact matches. Feel free to explore other career topics!"

        # Rule 3 Calculation: Did we find more courses in the DB than what we will display?
        # A simple heuristic: if initial grounded_courses > 6, they won't all be primary.
        has_more_in_catalog = (len(grounded_courses) > 6) if grounded_courses else False
        
        # Step 7: Final Renderer -> Skill Extraction Mode
        guidance_data = generate_final_response(
            user_question=message,
            guidance_plan=guidance_plan,
            grounded_courses=grounded_courses, 
            language=router_out.user_language,
            coverage_note=coverage_note,
            chat_history=chat_history,
            has_more_in_catalog=has_more_in_catalog # Rule 3
        )
        
        # Improved Role Type Detection
        target_role_lower = (router_out.target_role or "").lower()
        role_type = router_out.role_type or "non_technical"
        if any(x in target_role_lower for x in ["data", "scientist", "engineer", "developer", "backend", "analyst", "analysis", "programming", "software", "security", "cyber", "network"]):
            role_type = "technical"
        elif any(x in target_role_lower for x in ["designer", "ui", "ux", "creative", "art", "media", "3d", "modeling"]):
            role_type = "design"
        elif any(x in target_role_lower for x in ["manager", "lead", "soft skills", "communication", "leadership", "productivity"]):
            role_type = "soft_skills"

        # New Strict Response Processing
        response_text = guidance_data.get("answer", "")
        
        # 1. Courses: The LLM now returns the full filtered list directly
        recommended_courses_raw = guidance_data.get("recommended_courses", [])
        
        # We trust the Strict LLM output for grounding, but we still do a safety ID check
        # to ensure we can map back to our original objects if needed (though LLM returned full object).
        # Since strict prompt explicitly returns catalog objects, we can use them directly 
        # BUT we must convert them to the CourseDetail schema.
        
        api_courses = []
        for rc in recommended_courses_raw:
            api_courses.append(CourseDetail(
                course_id=str(rc.get("course_id")),
                title=rc.get("title"),
                level=rc.get("level"),
                category=rc.get("category"),
                instructor=rc.get("instructor"),
                duration_hours=float(rc.get("duration_hours") or 0),
                description=rc.get("description")[:200] if rc.get("description") else None,
                skills=rc.get("skills"),
                cover=rc.get("cover")
            ))
            
        # 2. Projects: Handled as "practice_tasks" (plain text) in strict mode
        # We accept them but wrap them in the Project schema for frontend compatibility
        practice_tasks = guidance_data.get("practice_tasks", [])
        api_projects = []
        
        for task in practice_tasks:
            # Task is a string, so we wrap it
            api_projects.append(ProjectDetail(
                title="Practice Task",
                level="All Levels",
                description=str(task), # The task text goes here
                skills=[]
            ))

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
                await db.flush() # Ensure ID is written before messages
            
            # Add messages
            db.add(ChatMessage(
                session_id=session_uuid, request_id=uuid.uuid4(), role="user", 
                content=message, intent=intent
            ))
            db.add(ChatMessage(
                session_id=session_uuid, request_id=uuid.uuid4(), role="assistant",
                content=response_text, intent=intent, retrieved_course_count=len(api_courses),
                latency_ms=latency_ms
            ))
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
        
        # Update Session Context (Simplified for Strict Mode)
        # We extracted skills implicitly via the retrieval step, but strict mode doesn't return separate 'skills' list top-level.
        # We can extract them from the recommended courses if needed, or just leave empty.
        
        update_session_context(
            str(session_uuid), 
            topic=router_out.target_role or "General", 
            role_type=role_type, 
            projects=[], # No rich projects to save in strict mode
            skills=[]
        )

        return ChatResponse(
            session_id=str(session_uuid),
            intent=intent,
            answer=response_text,
            courses=api_courses,
            projects=api_projects,
            request_id=str(uuid.uuid4())
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
