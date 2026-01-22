"""
Chat endpoint - main RAG pipeline with scope-gated retrieval.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ChatRequest, ChatResponse, ErrorResponse, CourseDetail, ErrorDetail, ChatSession, ChatMessage
import hashlib
from app.router import classify_intent, GroqUnavailableError
from app.retrieval import retrieve_by_exact_title, retrieve_by_semantic
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
        
        # Step 2: Router - classify intent and check scope
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
        
        # Step 3: Retrieval based on scope and intent
        catalog_results = []
        suggested_titles = []
        
        if not in_scope:
            # Out of scope - no retrieval
            logger.info("Query out of scope - skipping retrieval")
            catalog_results = []
            
        elif intent == "COURSE_DETAILS":
            # Exact/fuzzy title match only (no semantic to avoid drift)
            title_candidate = router_output.course_title_candidate or message
            course, suggestions = await retrieve_by_exact_title(db, title_candidate)
            
            if course:
                catalog_results = [course]
            else:
                suggested_titles = suggestions
                
        elif intent in ["SEARCH", "CAREER_GUIDANCE", "PLAN_REQUEST"]:
            # Semantic search with category filtering
            top_k = 10 if intent == "SEARCH" else 8
            
            # Build filters from target_categories
            filters = {}
            if target_categories:
                # We'll filter in retrieval by checking if course.category in target_categories
                filters["categories"] = target_categories
            
            catalog_results = await retrieve_by_semantic(
                db, 
                message, 
                top_k=top_k,
                filters=filters
            )
            
            # Additional filtering by target_categories if semantic search didn't apply it
            if target_categories and catalog_results:
                catalog_results = [
                    c for c in catalog_results
                    if c.category in target_categories or not c.category
                ][:top_k]
            
        elif intent in ["OUT_OF_SCOPE", "UNSAFE", "SUPPORT_POLICY"]:
            # No retrieval - empty catalog will trigger appropriate response
            catalog_results = []
        
        request_log["course_count"] = len(catalog_results)
        
        # Step 4: Generator - get LLM response (scope-aware)
        try:
            response_text = generate_response(
                user_question=message,
                in_scope=in_scope,
                intent=intent,
                target_categories=target_categories,
                catalog_results=catalog_results,
                suggested_titles=suggested_titles if not catalog_results else None,
                user_language=user_language
            )
        except GroqUnavailableError as e:
            # Generator failed - return 503 (no fallback)
            logger.error(f"Generator unavailable: {e}")
            raise HTTPException(
                status_code=503,
                detail={"error": "LLM unavailable", "component": "generator"}
            )
        
        # Step 5: Session management
        # Get or create session
        session_id_str = request.session_id
        if session_id_str:
            # Verify session exists
            try:
                session_uuid = uuid.UUID(session_id_str)
                stmt = select(ChatSession).where(ChatSession.id == session_uuid)
                result = await db.execute(stmt)
                session = result.scalar_one_or_none()
                if not session:
                    # Create new session with provided ID
                    session = ChatSession(id=session_uuid)
                    db.add(session)
                    await db.commit()
            except (ValueError, Exception):
                # Invalid UUID or error - create new session
                session = ChatSession()
                db.add(session)
                await db.commit()
                session_id_str = str(session.id)
        else:
            # Create new session
            session = ChatSession()
            db.add(session)
            await db.commit()
            session_id_str = str(session.id)
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        request_uuid = uuid.UUID(request_id)
        session_uuid = uuid.UUID(session_id_str)
        
        # Step 5b: Store user message in chat_messages
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
        
        # Store assistant message in chat_messages
        assistant_message_record = ChatMessage(
            session_id=session_uuid,
            request_id=request_uuid,
            role="assistant",
            content=response_text,
            intent=intent,
            retrieved_course_count=len(catalog_results),
            response_length=len(response_text),
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
                description=course.description[:200] if course.description else None
            )
            for course in catalog_results
        ]
        
        # Step 6: Return response
        logger.info(f"Chat completed: in_scope={in_scope}, intent={intent}, user_lang={user_language} | {len(catalog_results)} courses | {latency_ms}ms | request_id={request_id}")
        
        return ChatResponse(
            session_id=session_id_str,
            intent=intent,
            answer=response_text,
            courses=courses_list,
            error=None,
            request_id=request_id
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.exception(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
