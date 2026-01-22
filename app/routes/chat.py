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

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse, responses={503: {"model": ErrorResponse}})
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Main chat endpoint implementing scope-gated RAG pipeline:
    Input → Router (scope check) → Retrieval (if in-scope) → Groq Generator → Response
    
    Returns 503 if Groq LLM is unavailable (no fallback responses).
    """
    start_time = time.time()
    request_log = {"message_length": len(request.message)}
    
    try:
        # Step 1: Input validation
        message = request.message.strip()
        if not message or len(message) < 3:
            raise HTTPException(status_code=400, detail="Message too short")
            
        # Step 2: Session Management & Pagination (EARLY LOAD)
        # We need session memory *before* retrieval for follow-ups
        session_id_str = request.session_id
        session_uuid = None
        if session_id_str:
            try:
                session_uuid = uuid.UUID(session_id_str)
            except ValueError:
                session_uuid = uuid.uuid4()
        else:
            session_uuid = uuid.uuid4()
            
        # Get or create session to access memory
        stmt = select(ChatSession).where(ChatSession.id == session_uuid)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            session = ChatSession(id=session_uuid, session_memory={})
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
        session_memory = session.session_memory or {}
        
        # Step 3: Router - classify intent and check scope
        try:
            router_output = classify_intent(message)
            intent = router_output.intent
            in_scope = router_output.in_scope
            target_categories = router_output.target_categories
            user_language = router_output.user_language
            request_log["intent"] = intent
            request_log["in_scope"] = in_scope
            request_log["user_language"] = user_language
        except GroqUnavailableError as e:
            # Router failed - return 503 (no fallback)
            logger.error(f"Router unavailable: {e}")
            raise HTTPException(
                status_code=503, 
                detail={"error": "LLM unavailable", "component": "router"}
            )
        
        # --- LOGIC FOR PAGINATION & CONTEXT ---
        current_offset = 0
        PAGE_SIZE = 5
        
        search_query = message
        filters = {}
        
        # Determine effective intent and query state
        if intent == "FOLLOW_UP":
            # Restore previous context
            search_query = session_memory.get("last_skill_query") or message
            last_cat = session_memory.get("last_categories", [])
            if last_cat:
                filters["categories"] = last_cat
                target_categories = last_cat # Override router
            
            # Pagination: next page
            last_offset = session_memory.get("offset", 0)
            current_offset = last_offset + PAGE_SIZE
            logger.info(f"Follow-up detected. Paging {last_offset} -> {current_offset}. Query: {search_query}")
            
        elif intent in ["SEARCH", "SKILL_SEARCH", "CATEGORY_BROWSE"]:
            # New search -> reset offset
            current_offset = 0
            # Use keywords from router if available, else message
            search_query = " ".join(router_output.keywords) if router_output.keywords else message

        # Step 4: Retrieval based on scope and intent
        catalog_results = []
        suggested_titles = []
        
        if not in_scope:
            logger.info("Query out of scope - skipping retrieval")
            catalog_results = []
            
        elif intent == "COURSE_DETAILS":
            title_candidate = router_output.course_title_candidate or message
            catalog_results = await retrieve_courses(db, title_candidate, top_k=3)
            # If no results, suggestions?
            if not catalog_results:
                suggested_titles = [] # Placeholder if we had suggestion logic
                
        elif intent in ["SEARCH", "SKILL_SEARCH", "CATEGORY_BROWSE", "AVAILABILITY_CHECK", "FOLLOW_UP", "CAREER_GUIDANCE", "PLAN_REQUEST"]:
            
            catalog_results = await retrieve_courses(
                db, 
                search_query, 
                top_k=PAGE_SIZE,
                offset=current_offset,
                filters=filters
            )
            
        request_log["course_count"] = len(catalog_results)

        # Step 4.5: Fetch History (standard)
        try:
            history_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_uuid)
                .limit(50)
            )
            history_result = await db.execute(history_stmt)
            all_records = history_result.scalars().all()
            sorted_records = sorted(all_records, key=lambda x: x.created_at, reverse=True)
            history_records = sorted_records[:10][::-1]
            chat_history = [{"role": msg.role, "content": msg.content} for msg in history_records]
        except Exception as e:
            logger.warning(f"Failed to fetch history: {e}")
            chat_history = []

        # Step 5: Data Gate Check
        # For Search/Details, if no data found and not a follow-up (which might end), we might skip LLM?
        # Actually proper behavior is: if 0 results, pass to Generator to say "No results found".
        # But if strictly OUT_OF_SCOPE logic handles it.
        
        # Generator
        response_text = None
        DATA_DEPENDENT_INTENTS = ["SEARCH", "SKILL_SEARCH", "CAREER_GUIDANCE", "PLAN_REQUEST", "COURSE_DETAILS"]
        
        # If strict search and no results (and NOT a follow-up that just reached end), GATE it?
        # Actually contract says: "State clearly that no more courses available".
        # So we should let LLM handle the "No Data" case if it's a follow-up.
        # But if it's a NEW search and 0 results -> NO_DATA.
        
        if intent in DATA_DEPENDENT_INTENTS and not catalog_results and intent != "FOLLOW_UP":
             if user_language == "ar":
                response_text = "عذراً، لم أجد أي كورسات مطابقة في قاعدة البيانات لهذا الطلب.\nهل يمكنك تحديد مجال مختلف أو مهارة أخرى؟"
             else:
                response_text = "I'm sorry, I couldn't find any matching courses in the database for this request.\nCould you specify a different field or skill?"
        
        if not response_text:
            try:
                # Update memory state for next turn (pass to LLM for awareness)
                # But actually we update DB *after* success.
                next_memory = session_memory.copy()
                
                # Advance logic for next time
                if intent != "FOLLOW_UP" and intent in ["SEARCH", "SKILL_SEARCH", "CAREER_GUIDANCE", "CATEGORY_BROWSE"]:
                    next_memory["last_skill_query"] = search_query
                    next_memory["last_categories"] = target_categories
                    next_memory["offset"] = 0 
                elif intent == "FOLLOW_UP" and catalog_results:
                    next_memory["offset"] = current_offset 
                
                # Pass to generator with "session_memory" (we need to update generator sig if not already)
                # Wait, does generator accept session_memory? I need to check generator.py signature. 
                # Assuming I will update generator.py next step if needed, or if I assume it does. 
                # The user requirement implied updating system state, so I should pass it.
                
                generator_output = generate_response(
                    user_question=message,
                    in_scope=in_scope,
                    intent=intent,
                    target_categories=target_categories,
                    catalog_results=catalog_results,
                    suggested_titles=suggested_titles if not catalog_results else None,
                    user_language=user_language,
                    chat_history=chat_history,
                    # We pass the *current state* + *intent to update*? 
                    # Actually system_state.py needs to simply reflect the current page.
                    # So we pass next_memory? Or current? 
                    # The prompt says "You have access to SESSION_MEMORY". 
                    # It should probably see the memory that led to *these results*.
                    # So `last_skill_query` (current), `offset` (current).
                    session_memory={
                        "last_skill_query": search_query,
                        "offset": current_offset,
                        "page_size": PAGE_SIZE,
                        "last_categories": target_categories
                    }
                )
                
                response_text = generator_output.get("answer_md", "")
                selected_courses_data = generator_output.get("selected_courses", [])
                
                # STRICT RE-FILTERING
                if selected_courses_data:
                    selected_ids = {str(c.get("course_id")) for c in selected_courses_data}
                    catalog_results = [c for c in catalog_results if str(c.course_id) in selected_ids]
                elif generator_output.get("mode") == "NO_DATA":
                    catalog_results = []
                    
                # Update Session DB
                if session:
                    session.session_memory = next_memory
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(session, "session_memory")
                    await db.commit()
                    
            except GroqUnavailableError as e:
                logger.error(f"Generator unavailable: {e}")
                raise HTTPException(
                    status_code=503,
                    detail={"error": "LLM unavailable", "component": "generator"}
                )
                
        # Generate outgoing request ID
        request_id = str(uuid.uuid4())
        request_uuid = uuid.UUID(request_id)
        
        # Step 5b: Store logs
        latency_ms = int((time.time() - start_time) * 1000)
        user_msg_hash = hashlib.sha256(message.encode()).hexdigest()[:64]
        
        user_message_record = ChatMessage(
            session_id=session_uuid,
            request_id=request_uuid,
            role="user",
            content=message,
            user_message_hash=user_msg_hash,
            intent=intent
        )
        db.add(user_message_record)
        
        assistant_message_record = ChatMessage(
            session_id=session_uuid,
            request_id=request_uuid,
            role="assistant",
            content=response_text or "",
            intent=intent,
            retrieved_course_count=len(catalog_results),
            response_length=len(response_text) if response_text else 0,
            latency_ms=latency_ms
        )
        db.add(assistant_message_record)
        await db.commit()
        
        # Build courses array
        courses_list = [
            CourseDetail(
                course_id=str(course.course_id),
                title=course.title,
                level=course.level,
                category=course.category,
                instructor=course.instructor,
                duration_hours=course.duration_hours,
                description=course.description[:200] if course.description else None,
                skills=course.skills[:100] if course.skills else None,
                cover=course.cover
            )
            for course in catalog_results
        ]
        
        return ChatResponse(
            session_id=str(session_uuid),
            answer=response_text or "",
            courses=courses_list,
            intent=intent,
            request_id=request_id
        )

    except HTTPException as he:
        # Re-raise HTTP exceptions as is
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error in chat endpoint: {e}")
        # Return generic 500
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
