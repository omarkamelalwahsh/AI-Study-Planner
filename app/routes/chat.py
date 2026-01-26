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

logger = logging.getLogger(__name__)
router = APIRouter()

# Domain Blacklist to prevent cross-domain hallucinations (Ultra-Strict)
DOMAIN_BLACKLIST = {
    "technical": ["Graphic Design", "Digital Media", "Health & Wellness", "Banking Skills", "Customer Service", "Human Resources", "Leadership", "Sales", "Management", "General", "Project Management", "Personal Productivity", "General Office"],
    "design": ["Programming", "Hacking", "Data Security", "Networking", "Banking Skills", "Technology Applications", "Project Management", "Human Resources", "Sales", "Management"],
    "soft_skills": ["Programming", "Hacking", "Data Security", "Networking", "Web Development", "Mobile Development", "Data Analysis"]
}

def is_blacklisted(role_type: str, category: str) -> bool:
    if not role_type or not category:
        return False
    # Map role_type to blacklist key
    key = role_type.lower()
    if key in DOMAIN_BLACKLIST:
        return category in DOMAIN_BLACKLIST[key]
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

        # --- PATH B: STANDARD SEARCH / OTHER ---
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
        
        # New Feature: Project Ideas (integrated in guidance_data)
        project_data = {"projects": guidance_data.get("projects", [])}
        response_text = guidance_data.get("text", "")
        
        # Normalize Skills: Unique, Cap 4-6
        extracted_skills = list(dict.fromkeys(guidance_data.get("skills", [])))[:6]
        if len(extracted_skills) < 4 and intent == "CAREER_GUIDANCE":
            # Just keeping what we have if LLM returned fewer, but capping at max 6.
            pass

        # Tiered Display Logic (Cards vs Text Only)
        primary_ids = guidance_data.get("primary_course_ids", [])
        secondary_ids = guidance_data.get("secondary_course_ids", [])
        
        card_courses = []
        text_only_courses = []
        
        # Map IDs back to objects
        course_map = {str(c.get("course_id")): c for c in grounded_courses}
        
        # Improved Role Type Detection
        target_role_lower = (router_out.target_role or "").lower()
        role_type = router_out.role_type or "non_technical"
        if any(x in target_role_lower for x in ["data", "scientist", "engineer", "developer", "backend", "analyst", "analysis", "programming", "software", "security", "cyber", "network"]):
            role_type = "technical"
        elif any(x in target_role_lower for x in ["designer", "ui", "ux", "creative", "art", "media", "3d", "modeling"]):
            role_type = "design"
        elif any(x in target_role_lower for x in ["manager", "lead", "soft skills", "communication", "leadership", "productivity"]):
            role_type = "soft_skills"

        # Normalize extracted_skills (Lower + Clean) for the Code Filter
        clean_extracted_skills = [re.sub(r"[^a-z0-9\+\#\.]", " ", s.lower()).strip() for s in extracted_skills]

        # Filter by Blacklist + Rule: Code Decides (Semantic Precision)
        all_candidate_ids = primary_ids + secondary_ids
        for cid in all_candidate_ids:
            if cid in course_map:
                course = course_map[cid]
                cat = course.get("category")
                
                # 1. Blacklist (Hard Stop)
                if is_blacklisted(role_type, cat):
                    continue
                
                # 2. Rule: Code Decides (Mandatory for PRIMARY CARDS)
                if cid in primary_ids:
                    # Apply Hard Gate: Course MUST match at least one skill keyword
                    if hard_skill_gate(course, clean_extracted_skills):
                        # 3. Soft Guard: Block "Soft Domains" crossover for "Hard Role"
                        # If role is Technical/Design but category is Soft Skills/Leadership, block unless skill match is verified.
                        if role_type in ["technical", "design"] and cat in ["Soft Skills", "Leadership & Management", "Project Management", "Personal Development"]:
                            # We already matched a skill in hard_skill_gate, but for crossovers, we prioritize the role
                            pass 
                        
                        card_courses.append(course)
                    else:
                        # Fail: Drop to text or ignore (Here we just drop)
                        text_only_courses.append(course)
                else:
                    text_only_courses.append(course)

        all_display_courses = card_courses + text_only_courses
        grounded_courses = card_courses # Return cards as the primary list

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
                content=response_text, intent=intent, retrieved_course_count=len(grounded_courses),
                latency_ms=latency_ms
            ))
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")

        # Convert all_display_courses to schema for API response
        api_courses = []
        for c in all_display_courses: # Changed from grounded_courses to all_display_courses
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
            
        # Convert projects to schema
        from app.models import ProjectDetail
        api_projects = []
        for p in project_data.get("projects", []):
            if not isinstance(p, dict):
                continue
            
            # Defensive check for required fields to prevent Pydantic crash
            title = p.get("title") or p.get("description", "Untitled Project")[:30]
            level = p.get("level") or "Intermediate"
            description = p.get("description") or "Applying professional skills."
            
            api_projects.append(ProjectDetail(
                title=title,
                level=level,
                description=description,
                skills=p.get("skills", [])
            ))

        return ChatResponse(
            session_id=str(session_uuid),
            intent=intent,
            answer=response_text,
            courses=api_courses, # Now uses api_courses derived from all_display_courses
            projects=api_projects,
            request_id=str(uuid.uuid4())
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
