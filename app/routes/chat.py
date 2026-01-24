"""
Chat endpoint - main RAG pipeline with scope-gated retrieval.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models import ChatRequest, ChatResponse, ErrorResponse, CourseDetail, ErrorDetail, ChatSession, ChatMessage
import hashlib
from app.router import classify_intent, GroqUnavailableError
from app.retrieval import retrieve_courses
from app.generator import generate_response
import logging
import time
import uuid
import json
from groq import Groq
from app.config import settings
from app.router import GroqUnavailableError

logger = logging.getLogger(__name__)
router = APIRouter()

SKILL_TRANSLATOR_SYSTEM = """You are a translation and normalization service for a Course Search Engine.
Return JSON only.

Rules:
1. Input: List of mixed Arabic/English skills.
2. Output: "skills_en": List of specific, searchable English technical keywords.
3. OPTIMIZATION FOR SEARCH:
   - "البيانات" -> "Data Analysis" (not "Data")
   - "الذكاء الاصطناعي" -> "Artificial Intelligence"
   - "إدارة" -> "Project Management" or "Business Management" (not "Management")
   - Avoid stopwords.
   - Use canonical industry terms.

Return:
{"skills_en":["Skill1", "Skill2"]}"""


def wants_courses_for_listed_skills(msg: str) -> bool:
    m = (msg or "").strip().lower()
    cues = [
         "هل لكل", "لكل مهاره", "لكل مهارة", "كل مهارة", "كل مهاره",
         "ليها كورسات", "ملهاش كورسات", "والي ملهاش", "واللي ملهاش",
         "كورسات للمهارات", "courses for these skills"
    ]
    return any(c in m for c in cues)


async def retrieve_for_each_skill(db, skills_en: list[str], top_k_per_skill: int = 2):
    results = []
    for sk in skills_en:
        hits = await retrieve_courses(db, sk, top_k=top_k_per_skill, offset=0, filters={})
        results.append((sk, hits))
    return results


async def translate_skills_to_english(skills: list[str]) -> list[str]:
    client = Groq(api_key=settings.groq_api_key)
    payload = json.dumps({"skills": skills}, ensure_ascii=False)

    try:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SKILL_TRANSLATOR_SYSTEM},
                {"role": "user", "content": payload},
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        skills_en = data.get("skills_en") or []
        # sanitize
        out = []
        for s in skills_en:
            s2 = (s or "").strip()
            if s2 and s2 not in out:
                out.append(s2)
        # Ensure parity with input list length for mapping
        # If lengths differ, we might lose alignment, so we try to keep them aligned or truncate
        return out
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return skills # Fallback




@router.post("/chat", response_model=ChatResponse, responses={503: {"model": ErrorResponse}})

async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Main chat endpoint implementing Multi-Layer RAG pipeline:
    Layer 0: Normalization & Gate (wants_courses?)
    Layer 1: Router (Classify Topic)
    Layer 2: Retrieval (Unified Grounding)
    Layer 3: Generator (Full Access + Safe Mode)
    Layer 4: Validator (Structure Check)
    """
    start_time = time.time()
    
    try:
        # Step 1: Input Normalization (Layer 0)
        from app.utils.normalization import normalize_text, wants_courses, detect_language
        
        raw_message = request.message
        message = normalize_text(raw_message)
        if not message or len(message) < 2:
            raise HTTPException(status_code=400, detail="Message too short")
            
        user_wants_courses = wants_courses(message)
        
        # Step 2: Session Management
        session_id_str = request.session_id
        session_uuid = uuid.UUID(session_id_str) if session_id_str else uuid.uuid4()
        
        stmt = select(ChatSession).where(ChatSession.id == session_uuid)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            session = ChatSession(id=session_uuid, session_memory={})
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
        session_memory = session.session_memory or {}
        
        # Step 3: Router (Layer 1)
        # We still use the router to get keywords and category, but we don't let it block retrieval.
        try:
            router_output = classify_intent(message)
            intent = router_output.intent
            target_categories = router_output.target_categories
            user_language = router_output.user_language or detect_language(message)
            
            # [NEW] Force CAREER_GUIDANCE for "Learn/Become" queries to ensure DEFINITION + PATH
            # patterns: "learn", "start", "become", "road map", "guide", "teaching", "teach", "تعلم", "ابدأ", "خارطة", "مسار", "كيف", "عاوز ابقي", "عايز ابقي", "عايز اتعلم", "عاوز اتعلم"
            edu_triggers = ["learn", "start", "become", "roadmap", "guide", "teaching", "teach", "تعلم", "ابدأ", "خارطة", "مسار", "كيف", "عاوز ابقي", "عايز ابقي", "عايز اتعلم", "عاوز اتعلم"]
            if any(t in message.lower() for t in edu_triggers):
                intent = "CAREER_GUIDANCE"

            # If user explicitly wants courses, override intent to SEARCH/BROWSE if it was GUIDANCE
            # [MODIFIED] We allow CAREER_GUIDANCE to proceed even if user wants courses, because Pattern 2 handles courses gracefully.
            if user_wants_courses and intent in ["PLAN_REQUEST", "GREETING"] and intent != "CAREER_GUIDANCE":
                 # Only demographics/greeting go to pure search. Educational stays Guidance.
                intent = "COURSE_SEARCH"
                
        except GroqUnavailableError:
            # Fallback if router fails
            from app.models import RouterOutput
            # Default to Guidance for robustness
            intent = "CAREER_GUIDANCE"
            target_categories = []
            user_language = detect_language(message)
            router_output = RouterOutput(
                in_scope=True, intent=intent, target_categories=[], 
                user_language=user_language, keywords=[message]
            )

        # --- PAGINATION LOGIC ---
        PAGE_SIZE = 5
        current_offset = 0
        filters = {}
        
        # [NEW] Intercept "Courses for these skills"
        if wants_courses_for_listed_skills(message):
            last_skills = session_memory.get("last_skills_raw") or []
            if not last_skills:
                 # Fallback if no skills in memory
                 pass # Continue to normal generator flow to say "Please tell me the skills first"
            else:
                 logger.info(f"Detected skill-based lookup for: {last_skills}")
                 skills_en = await translate_skills_to_english(last_skills)
                 per_skill = await retrieve_for_each_skill(db, skills_en, top_k_per_skill=2)
                 
                 # Deduplicate courses for Cards
                 final_courses = []
                 seen_ids = set()
                 
                 # Prepare text sections
                 found_lines = []
                 missing_lines = []
                 
                 for ar_skill, en_skill in zip(last_skills, skills_en):
                     # Search hits
                     hits = next((h for s, h in per_skill if s == en_skill), [])
                     
                     if hits:
                         titles = []
                         for c in hits:
                             if c.course_id not in seen_ids:
                                 final_courses.append(c)
                                 seen_ids.add(c.course_id)
                             titles.append(c.title)
                         
                         # Add to found section with short summary
                         titles_str = ", ".join(titles)
                         found_lines.append(f"- **{ar_skill}** ({en_skill}): يتوفر {len(hits)} كورس.")
                     else:
                         missing_lines.append(f"- **{ar_skill}** ({en_skill})")
                 
                 # Construct final message
                 response_parts = ["لقد بحثت لك عن كورسات لهذه المهارات:"]
                 
                 if found_lines:
                     response_parts.append("\n**✅ مهارات لها كورسات (طالع الكروت بالأسفل):**")
                     response_parts.extend(found_lines)
                     
                 if missing_lines:
                     response_parts.append("\n**⚠️ مهارات لم نجد لها كورسات مباشرة حالياً:**")
                     response_parts.extend(missing_lines)
                     response_parts.append("\n*نصيحة: يمكنك البحث عن هذه المهارات بشكل أوسع أو دمجها مع مهارات أخرى.*")
                     
                 response_text = "\n".join(response_parts)
                 
                 # Quick save interaction
                 latency_ms = int((time.time() - start_time) * 1000)
                 db.add(ChatMessage(
                    session_id=session_uuid, request_id=uuid.uuid4(), role="user", 
                    content=message, user_message_hash=hashlib.sha256(message.encode()).hexdigest()[:64], 
                    intent="SKILL_SEARCH"
                 ))
                 db.add(ChatMessage(
                    session_id=session_uuid, request_id=uuid.uuid4(), role="assistant",
                    content=response_text, intent="SKILL_SEARCH", retrieved_course_count=len(final_courses),
                    latency_ms=latency_ms
                 ))
                 await db.commit()
                 
                 # Return immediately
                 courses_list = [
                    CourseDetail(
                        course_id=str(c.course_id),
                        title=c.title,
                        level=c.level,
                        category=c.category,
                        instructor=c.instructor,
                        duration_hours=c.duration_hours,
                        description=c.description[:200] if c.description else None,
                        skills=c.skills[:100] if c.skills else None,
                        cover=c.cover
                    )
                    for c in final_courses
                 ]
                 return ChatResponse(
                    session_id=str(session_uuid),
                    answer=response_text,
                    courses=courses_list,
                    intent="SKILL_SEARCH",
                    request_id=str(uuid.uuid4())
                 )

        # Determine query for retrieval
        search_query = message
        extracted_skills = None # [NEW] Scope initialization
        skill_course_map = {}
        ordered_skills = []
        
        if intent == "FOLLOW_UP":
            # Restore context
            search_query = session_memory.get("last_skill_query") or message
            last_cat = session_memory.get("last_categories", [])
            if last_cat:
                filters["categories"] = last_cat
                target_categories = last_cat
            
            # Next page
            last_offset = session_memory.get("offset", 0)
            current_offset = last_offset + PAGE_SIZE
        
        elif intent == "AVAILABILITY_CHECK":
            # Check if user provided new keywords or if we should use context
            # If keywords are just "courses" or empty, use history
            is_generic_check = not router_output.keywords or all(k in ["courses", "corse", "cours", "كورس", "كورسات"] for k in router_output.keywords)
            
            if is_generic_check and session_memory.get("last_skill_query"):
                logger.info("Generic availability check detected, using context.")
                search_query = session_memory.get("last_skill_query")
                # Do NOT advance offset (start from 0 to show top results)
                current_offset = 0
                
                last_cat = session_memory.get("last_categories", [])
                if last_cat:
                    filters["categories"] = last_cat
                    target_categories = last_cat
            else:
                 # Specific check (e.g. "Do you have python courses?")
                 current_offset = 0
                 if router_output.keywords:
                     search_query = " ".join(router_output.keywords)
        else:
            # New query
            current_offset = 0
            # Use keywords if available and robust, else message
            # For strict course search, keywords are better. For broad guidance, message is fine.
            if router_output.keywords:
                search_query = " ".join(router_output.keywords)
                
            # [NEW] Layer 1.5: Skill Extraction for Career Guidance (Structured)
            skill_course_map = {}
            ordered_skills = []
            catalog_results = [] # Initialize here to allow appending found courses
            
            if intent == "CAREER_GUIDANCE":
                from app.skills import analyze_career_request
                from app.utils.skill_index import find_skill_matches
                from app.models import Course
                
                # 1. Analyze Request (Role & Areas)
                analysis = analyze_career_request(message)
                target_role = analysis.get("target_role", "Professional")
                skill_areas = analysis.get("skill_areas", [])
                correction_note = analysis.get("correction") # [NEW]
                
                # Store target role & correction
                session_memory["locked_role"] = target_role
                if correction_note:
                    session_memory["typo_correction"] = correction_note
                
                logger.info(f"Career Analysis: Role={target_role}, Areas={len(skill_areas)}")
                
                # 2. Retrieval per Area (DEEP SEARCH Strategy)
                for area in skill_areas:
                    area_name = area.get("area_name", "General")
                    keywords = area.get("search_keywords", [])
                    
                    found_for_area = [] # List of course objects
                    
                    # Track evidence: how did we find this course?
                    # course_id -> {"queries": [], "score": 0}
                    area_evidence = {} 

                    # Execute ALL queries for the area (Deep Search)
                    for kw in keywords:
                        matches = find_skill_matches(kw)
                        if matches:
                            # Consider top 2 matches for EACH query to maximize recall
                            top_matches = matches[:2]
                            
                            for m in top_matches:
                                # Extract ID
                                course_ids = m.get("course_ids", [])[:15] # [EXPANDED] Up to 15 courses per match to maximize recall
                                score = m.get("score", 0)
                                match_key = m.get("key", "")
                                
                                for item in course_ids:
                                    tid = item.get("course_id") if isinstance(item, dict) else item
                                    tid_str = str(tid)
                                    
                                    # Record evidence
                                    if tid_str not in area_evidence:
                                        area_evidence[tid_str] = {"queries": set(), "score": score}
                                    
                                    area_evidence[tid_str]["queries"].add(f"{kw} (matched '{match_key}')")
                                    # specific logic: keep max score
                                    if score > area_evidence[tid_str]["score"]:
                                        area_evidence[tid_str]["score"] = score
                    
                    # Fetch Courses if we have candidates
                    candidate_ids = list(area_evidence.keys())
                    if candidate_ids:
                         valid_uuids = []
                         # [EXPANDED] Fetch more candidates since we want to show multiple
                         for cid in candidate_ids[:40]: 
                             try: valid_uuids.append(uuid.UUID(cid))
                             except: pass
                         
                         if valid_uuids:
                             stmt = select(Course).where(Course.course_id.in_(valid_uuids))
                             res = await db.execute(stmt)
                             courses = res.scalars().all()
                             
                             # Sort by Evidence Score desc
                             courses_sorted = sorted(
                                 courses, 
                                 key=lambda c: area_evidence.get(str(c.course_id), {}).get("score", 0), 
                                 reverse=True
                             )
                             
                             found_for_area = courses_sorted
                    
                    # [STRICT GROUNDING RULE]
                    # Only add this Area if we actually found courses for it.
                    if found_for_area:
                        skill_course_map[area_name] = []
                        # [EXPANDED] Add top 10 courses per Area (was 3)
                        # The Generator LLM will control pagination/formatting if 10 is too many,
                        # but we must provide them to context.
                        for c in found_for_area[:10]:
                            cid_str = str(c.course_id)
                            evidence = area_evidence.get(cid_str, {})
                            queries_str = ", ".join(list(evidence.get("queries", []))[:2])
                            
                            skill_course_map[area_name].append({
                                "course_id": cid_str, 
                                "title": c.title, 
                                "level": c.level, 
                                "instructor": c.instructor, 
                                "reason": f"Matched via: {queries_str}" 
                            })
                        
                        # Add to Global Context (Deduplicated)
                        for c in found_for_area:
                            if not any(x.course_id == c.course_id for x in catalog_results):
                                catalog_results.append(c)
                                
                        # Track order for display
                        ordered_skills.append(area_name)
                    else:
                        logger.info(f"Dropping area '{area_name}' due to no course matches.")

                # [GLOBAL SEARCH RULE]
                # If we did Career Guidance search, we ignore category filters for the Retrieval Layer
                # effectively bypassing the "General" filter if it was set.
                if catalog_results:
                     target_categories = [] # Clear filters so Layer 2 doesn't wipe our results
                     filters = {} 

                if not catalog_results:
                     logger.info("No courses found via Career Analysis Loop.")

                if not catalog_results:
                     logger.info("No courses found via Career Analysis Loop.")

        
        # Step 4: Retrieval (Layer 2) - UNIFIED GROUNDING
        # We always attempt to retrieve relevant courses to ground the LLM, 
        # unless it's a Greeting or clearly out of scope (but we let LLM decide scope usually).
        
        # catalog_results initialized above
        suggested_titles = []
        
        # Filter logic
        if target_categories:
             # Basic cleanup for "General"
             if "General" in target_categories and len(target_categories) > 1:
                 target_categories = [c for c in target_categories if c != "General"]
             filters["categories"] = target_categories

            # Retrieve
        if intent == "COURSE_DETAILS":
            # Specific case
            title_candidate = router_output.course_title_candidate or message
            catalog_results = await retrieve_courses(db, title_candidate, top_k=3)
        else:
            # General search / guidance grounding
            catalog_results = await retrieve_courses(
                db, 
                search_query, 
                top_k=PAGE_SIZE, 
                offset=current_offset if user_wants_courses else 0, # Only paginate if listing
                filters=filters
            )

        # [NEW] Step 4.5: Fetch Chat History for Context
        # We fetch the last 6 messages to give the LLM conversation context
        history_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_uuid)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
        )
        history_res = await db.execute(history_stmt)
        recent_messages = history_res.scalars().all()
        # Convert to list of dicts {role, content} and reverse to chronological order
        chat_history_dicts = []
        for m in reversed(recent_messages):
            chat_history_dicts.append({"role": m.role, "content": m.content})


        # Step 5: Generator (Layer 3) - Unified Mode
        try:
            # Prepare next memory state
            next_memory = session_memory.copy()
            if intent != "FOLLOW_UP":
                next_memory["last_skill_query"] = search_query
                next_memory["last_categories"] = target_categories
                next_memory["offset"] = 0
            elif catalog_results: # only advance offset if we got results
                 next_memory["offset"] = current_offset

            # Call Generator
            # We pass 'user_wants_courses' to help the LLM decide formatting (List vs Text)
            generator_output = generate_response(
                user_question=message,
                in_scope=True, # We explicitly allow full access now, relying on retrieved data relevance
                intent=intent,
                target_categories=target_categories,
                catalog_results=catalog_results,
                suggested_titles=suggested_titles,
                user_language=user_language,
                chat_history=chat_history_dicts, # [MODIFIED] Pass actual history
                session_memory=next_memory,
                user_wants_courses=user_wants_courses, # New Param
                extracted_skills=extracted_skills, # Legacy param, keep for now or pass list
                skill_course_map=skill_course_map, # [NEW] Structured map
                ordered_skills=ordered_skills # [NEW] Original skills order
            )
            
            response_text = generator_output.get("answer_md", "")
            selected_courses_data = generator_output.get("selected_courses", [])
            
            # [NEW] Save skills to memory if present
            skills_ordered = generator_output.get("skills_ordered") or []
            if skills_ordered:
                next_memory["last_skills_raw"] = skills_ordered[:20]
                # Force update session to save this new memory key
                session.session_memory = next_memory
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(session, "session_memory")
                await db.commit()
            
            # Step 6: Validator (Layer 4)
            # Ensure strictly that returned courses are in catalog_results
            final_courses = []
            if selected_courses_data:
                valid_ids = {str(c.course_id) for c in catalog_results}
                for c in selected_courses_data:
                    cid = str(c.get("course_id"))
                    if cid in valid_ids:
                        # Find original to ensure data integrity
                        original = next((x for x in catalog_results if str(x.course_id) == cid), None)
                        if original:
                            final_courses.append(original)
            
            # Update Session
            if session:
                session.session_memory = next_memory
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(session, "session_memory")
                await db.commit()
                
            # Logging
            latency_ms = int((time.time() - start_time) * 1000)
            user_msg_hash = hashlib.sha256(message.encode()).hexdigest()[:64]
            
            # Save history (simplified)
            db.add(ChatMessage(
                session_id=session_uuid, request_id=uuid.uuid4(), role="user", 
                content=message, user_message_hash=user_msg_hash, intent=intent
            ))
            db.add(ChatMessage(
                session_id=session_uuid, request_id=uuid.uuid4(), role="assistant",
                content=response_text, intent=intent, retrieved_course_count=len(catalog_results),
                latency_ms=latency_ms
            ))
            await db.commit()
            
            # Build Response
            courses_list = [
                CourseDetail(
                    course_id=str(c.course_id),
                    title=c.title,
                    level=c.level,
                    category=c.category,
                    instructor=c.instructor,
                    duration_hours=c.duration_hours,
                    description=c.description[:200] if c.description else None,
                    skills=c.skills[:100] if c.skills else None,
                    cover=c.cover
                )
                for c in final_courses
            ]
            
            return ChatResponse(
                session_id=str(session_uuid),
                answer=response_text,
                courses=courses_list,
                intent=intent,
                request_id=str(uuid.uuid4())
            )

        except GroqUnavailableError as e:
            raise HTTPException(status_code=503, detail="LLM Unavailable")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
