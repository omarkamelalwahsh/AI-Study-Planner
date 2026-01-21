import re
import uuid
import logging
import asyncio
from typing import AsyncGenerator, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.llm.factory import get_llm
from app.services.retrieval_service import DBRetrievalService
from app.models import ChatSession as DBChatSession, ChatMessage
from app.utils.normalize import normalize_text
from app.config.learning_mapping import LEARNING_MAPPING

logger = logging.getLogger("chat_service")
logger.setLevel(logging.INFO)

EXPLAIN_TRIGGERS = re.compile(r"(اشرح|شرح|ما هو|يعني ايه|عرّف|تعريف)", re.IGNORECASE)


def detect_lang(user_text: str) -> str:
    """Enhanced language detection based on character counting (AR vs Latin)."""
    s = (user_text or "").strip()
    if not s:
        return "en"
    
    arabic_chars = sum(1 for c in s if '\u0600' <= c <= '\u06FF')
    latin_chars = sum(1 for c in s if c.isascii() and c.isalpha())
    
    return "ar" if arabic_chars > latin_chars else "en"


def is_learning_request(text: str) -> bool:
    """Check if the user intent is specifically about learning/studying."""
    triggers = [
        "learn", "study", "تعلم", "عاوز اتعلم", "عايز اتعلم", "أتعلم", "شرح", "كورس", "كورسات"
    ]
    t = text.lower()
    # Check for direct word matches or multi-word triggers
    return any(trigger in t for trigger in triggers)


def safe_uuid(session_id: str) -> str:
    try:
        uuid.UUID(session_id)
        return session_id
    except Exception:
        return str(uuid.uuid4())


import json

def enforce_guardrails(raw_input: str | dict, allowed_course_ids: set, consent_to_show_full_list: bool | None):
    # ✅ NEW: accept dict OR string
    if isinstance(raw_input, dict):
        data = raw_input
    else:
        try:
            data = json.loads(raw_input)
        except json.JSONDecodeError:
            return {
                "assistant_message": str(raw_input),
                "courses": [],
                "consent_needed": False,
                "language": "en",
                "intent": "fallback",
            }
        
    # 1) Courses must be list
    courses = data.get("courses") or []
    if not isinstance(courses, list):
        courses = []

    # 2) Consent gating
    if not consent_to_show_full_list:
        courses = courses[:2]
        data["consent_needed"] = True

    # 3) Prevent Hallucination: course_id must be in candidates
    filtered = []
    for c in courses:
        cid = c.get("course_id") or c.get("id")
        # Ensure we check against string IDs
        if cid and str(cid) in allowed_course_ids:
            # Fill missing optional arrays
            c.setdefault("prerequisites", [])
            c.setdefault("missing_skills", [])
            c.setdefault("duration_hours", 0)
            c.setdefault("readiness", "Unknown")
            c.setdefault("reason", "مناسب لطلبك")
            c.setdefault("category", "General")
            c.setdefault("score", 0.5)
            # Map id -> course_id if needed by schema (CourseOut uses alias="id" to map input "id", so keeping "id" is fine? 
            # Or if LLM returned "course_id", CourseOut needs "id" in input dict if populating by name?
            # CourseOut(course_id=..., title=...) or CourseOut(id=..., title=...)
            # ConfigDict(populate_by_name=True) allows using field name `course_id`.
            # If input has `id`, it maps to `course_id`. If input has `course_id` (and no `id`), it works with populate_by_name=True?
            # Yes. Let's ensure we have a consistent key for CourseOut to consume.
            # If we set c["id"] = cid, it will work.
            if "id" not in c and "course_id" in c:
                c["id"] = c["course_id"]
            
            filtered.append(c)
    data["courses"] = filtered

    # 4) follow_up_question / assistant_message rule:
    if data.get("follow_up_question"):
        data["assistant_message"] = data.get("assistant_message", "").replace("؟", "").strip()

    # 5) study_plan rule
    if not isinstance(data.get("study_plan"), list):
        data["study_plan"] = []

    # 6) notes
    if not isinstance(data.get("notes"), dict):
        data["notes"] = {}

    return data



def is_broad_intent(user_text: str, lang: str) -> bool:
    t = (user_text or "").strip().lower()
    if not t:
        return False
    en_patterns = [
        "learn programming", "learn coding", "become a programmer",
        "i want to learn programming", "i want to learn coding",
        "i want to become a developer", "become a developer",
        "learn software"
    ]
    ar_patterns = [
        "عاوز اتعلم برمجة", "عايز اتعلم برمجة", "عاوز أتعلم برمجة", "عايز أتعلم برمجة",
        "اتعلم برمجة", "اتعلم كود", "اتعلم coding", "مطور", "مبرمج"
    ]
    if lang == "en":
        return any(p in t for p in en_patterns) and len(t.split()) <= 10
    else:
        return any(p in t for p in ar_patterns) and len(t.split()) <= 10


class ChatSessionState(BaseModel):
    # stage drives the whole flow
    stage: str = "choose_path"  # choose_path|choose_track|choose_level|recommend_courses|ask_hours|ask_weeks|build_plan
    last_question_type: Optional[str] = None
    active_category: Optional[str] = None
    active_path: Optional[str] = None # This is the "track" chosen by the user
    user_level: Optional[str] = None
    hours_per_week: Optional[int] = None
    weeks: Optional[int] = None
    last_lang: Optional[str] = None
    consent_given: Optional[bool] = None
    goal: Optional[str] = None
    skills: List[str] = []
    want_plan: Optional[str] = None # "yes" or "no"
    metadata: dict = {} # Session metadata


class PartialJSONStreamer:
    """Helper to incrementally extract a specific key's value from a streaming JSON string."""
    def __init__(self, target_key: str = "assistant_message"):
        self.target_key = target_key
        self.buffer = ""
        self.found_key = False
        self.in_value = False
        self.value_buffer = ""
        self.sent_index = 0

    def process_chunk(self, chunk: str) -> str:
        self.buffer += chunk
        
        if not self.found_key:
            # Look for "assistant_message": "
            pattern = f'"{self.target_key}"\\s*:\\s*"'
            match = re.search(pattern, self.buffer)
            if match:
                self.found_key = True
                self.in_value = True
                # Start after the matched pattern
                self.value_buffer = self.buffer[match.end():]
                self.buffer = "" # Clear buffer once key is found
        elif self.in_value:
            self.value_buffer += chunk
            # Check if we hit the closing quote (not escaped)
            # This is a bit naive but usually works for LLM JSON
            closing_match = re.search(r'(?<!\\)"', self.value_buffer)
            if closing_match:
                self.in_value = False
                res = self.value_buffer[:closing_match.start()]
                delta = res[self.sent_index:]
                self.sent_index = len(res)
                return delta
        
        if self.in_value:
            delta = self.value_buffer[self.sent_index:]
            self.sent_index = len(self.value_buffer)
            return delta
        
        return ""


class ChatService:
    def __init__(self, course_csv_path: Optional[str] = None):
        self.llm = get_llm()
        self.retriever = DBRetrievalService()

    def _update_stage(self, state: ChatSessionState, is_plan_request: bool):
        """Update stage based on current state and user intent"""
        if is_plan_request and state.active_path and state.user_level:
            if state.hours_per_week is None:
                state.stage = "ask_hours"
                return
            if state.weeks is None:
                state.stage = "ask_weeks"
                return
            state.stage = "build_plan"
            return

        if not state.active_category and not state.active_path:
            state.stage = "choose_path"
        elif state.active_category and not state.active_path:
            state.stage = "choose_track"
        elif state.active_path and not state.user_level:
            # Check if we already asked level to avoid repetition
            last_q = state.metadata.get("last_question_asked", "")
            if "مستوى" in last_q or "level" in last_q.lower():
                state.stage = "choose_level" 
            else:
                state.stage = "choose_level"
        else:
            state.stage = "recommend_courses"

    def _extract_numbers(self, text: str) -> Optional[int]:
        """Extract first number from text"""
        import re
        m = re.search(r"(\d+)", text or "")
        return int(m.group(1)) if m else None

    def ensure_session(self, db: Session, session_id: str) -> DBChatSession:
        session_uuid = uuid.UUID(session_id)
        db_session = db.query(DBChatSession).filter(DBChatSession.id == session_uuid).first()
        if db_session:
            return db_session
        logger.info(f"Creating new session: {session_uuid}")
        initial_state = ChatSessionState()
        db_session = DBChatSession(
            id=session_uuid,
            state=initial_state.model_dump(),
            title="New Chat",
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session

    def persist_user_message(self, db: Session, session_id: str, content: str) -> ChatMessage:
        session_uuid = uuid.UUID(session_id)
        user_msg = ChatMessage(session_id=session_uuid, role="user", content=content)
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)
        return user_msg

    async def handle_message(self, session_id: str, message: str, db: Session) -> AsyncGenerator[dict | str, None]:
        session_uuid = uuid.UUID(session_id)
        db_session = db.query(DBChatSession).filter(DBChatSession.id == session_uuid).first()
        if not db_session:
            db_session = self.ensure_session(db, session_id)

        current_state = ChatSessionState(**(db_session.state or {}))
        
        # --- Language Persistence Logic ---
        detected = detect_lang(message)
        # If message is very short (likely "sql", "python", "no"), stick to last language
        if len(message.strip().split()) <= 2 and current_state.last_lang:
            lang = current_state.last_lang
        else:
            lang = detected
            current_state.last_lang = lang

        # 1. Update Consent based on user reply
        if current_state.last_question_type == "consent_request":
            if self._is_confirmation(message):
                current_state.consent_given = True
                current_state.last_question_type = None 
            elif self._is_negation(message):
                current_state.consent_given = False
                current_state.last_question_type = None

        # 2. Extract structured info from message
        self._update_state_from_message(message, current_state)

        # 3. Broad Intent / Out of Scope checks

        # 4. Extract plan data from message when stage expects it
        is_plan_request = self._is_study_plan_request(message)
        
        if current_state.stage == "ask_hours":
            n = self._extract_numbers(message)
            if n is not None:
                current_state.hours_per_week = n
                logger.info(f"Hours per week set: {n}")
        elif current_state.stage == "ask_weeks":
            n = self._extract_numbers(message)
            if n is not None:
                current_state.weeks = n
                logger.info(f"Weeks set: {n}")

        # 5. Update stage (Minimal impact now, mostly for internal logging)
        self._update_stage(current_state, is_plan_request)
        
        # 6. Retrieve for any valid query
        catalog = []
        rag_query = current_state.active_path or current_state.active_category or message
        if rag_query:
            catalog = self.retriever.get_best_matches(rag_query, limit=20)

        # 7. Build Messages for LLM
        from app.core.prompts import SYSTEM_PROMPT
        
        # Inject state summary for context-awareness (Definition + Leveled Courses focus)
        context_data = {
            "stage": current_state.stage,
            "active_path": current_state.active_path,
            "user_level": current_state.user_level,
            "catalog": catalog
        }
        
        history_objs = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_uuid)
            .order_by(desc(ChatMessage.created_at))
            .limit(10)
            .all()
        )
        history_objs.reverse()
        history_dicts = [{"role": m.role, "content": m.content} for m in history_objs]
        
        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages_payload.extend(history_dicts)
        
        import json
        context_str = json.dumps(context_data, ensure_ascii=False)
        final_user_content = f"{message}\n\nCONTEXT_DATA:\n{context_str}"
        messages_payload.append({"role": "user", "content": final_user_content})

        # 8. Call LLM (Non-Streaming for Production Stability)
        full_response_text = ""
        try:
             async for chunk in self.llm.stream(messages_payload, temperature=0.2):
                full_response_text += chunk
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            yield {"message": "Sorry, I encountered an error connecting to the AI.", "courses": [], "study_plan": []}
            return

        # 9. Parse & Validate
        from app.schemas.recommendation import LLMRecommendationResponse
        
        parsed_response: Optional[LLMRecommendationResponse] = None
        try:
            # 1. Robust regex extraction
            json_match = re.search(r"(\{.*\}|\[.*\])", full_response_text, re.DOTALL)
            clean_text = json_match.group(1) if json_match else full_response_text.strip()
            
            # 2. Guardrails Setup
            guarded_data = json.loads(clean_text)
            allowed_ids = set()
            for item in catalog:
                if isinstance(item, dict):
                     allowed_ids.add(str(item.get("course_id", "")))
                else:
                     if hasattr(item, "course_id"):
                          allowed_ids.add(str(item.course_id))

            # Enforce guardrails on courses
            # Enforce guardrails on courses
            # from app.services.guardrails import enforce_guardrails # REMOVED: Defined locally
            enforce_guardrails(guarded_data, allowed_ids, current_state.consent_given)

            # 3. Model Validation
            parsed_response = LLMRecommendationResponse.model_validate(guarded_data)
           
            # --- STATE UPDATE FROM LLM NOTES ---
            notes = getattr(parsed_response, "notes", {})
            if isinstance(notes, dict):
                if notes.get("chosen_category"): current_state.active_category = notes["chosen_category"]
                if notes.get("chosen_track"): current_state.active_path = notes["chosen_track"]
                if notes.get("user_level"): current_state.user_level = notes["user_level"]
                current_state.metadata["last_question_asked"] = notes.get("last_question_asked") or ""

            # 1. Reason Validation
            for c in parsed_response.courses:
                if not c.reason or not c.reason.strip():
                     c.reason = f"Matches your interest in {parsed_response.intent.replace('_', ' ').title()}."

            # 2. Intent Validation
            valid_intents = ["choose_path", "choose_track", "choose_level", "recommend_courses", "study_plan_request", "study_plan", "assessment_question", "assessment_result", "fallback"]
            if parsed_response.intent not in valid_intents:
                parsed_response.intent = "fallback"

        except Exception as e:
            logger.error(f"JSON Parse/Validation Error: {str(e)[:200]}\nRaw: {full_response_text[:300]}...")
            
            # --- FALLBACK: Try to rescue at least the text ---
            try:
                # If it's valid JSON but just failed Pydantic validation
                data = json.loads(clean_text) if 'clean_text' in locals() else {}
                msg = data.get("assistant_message") or data.get("message")
                follow_up = data.get("follow_up_question") or data.get("follow_up")
                
                if msg:
                    text_resp = f"{msg}\n\n{follow_up}" if follow_up else msg
                    yield {"text": text_resp, "courses": [], "study_plan": [], "intent": "fallback"}
                    self._persist_assistant_response(db, session_uuid, text_resp, current_state, db_session)
                    return
            except:
                pass

            # Final safety: yield the raw text if it's not JSON, or a friendly error
            if "{" not in full_response_text:
                yield full_response_text
            else:
                yield "معلش، حصلت مشكلة بسيطة في عرض الرد. ممكن تحاول تاني؟"
                
            self._persist_assistant_response(db, session_uuid, full_response_text, current_state, db_session)
            return

        # 8. Update State
        if parsed_response.consent_needed:
            current_state.last_question_type = "consent_request"
        
        # 9. Render & Stream
        response_payload = self._render_recommendation(parsed_response)
        
        # Serialize to JSON-compatible dict (Pydantic models need dump)
        final_payload = {
            "text": response_payload["text"], # Restored text for non-streaming
            "courses": [c.model_dump() for c in response_payload["courses"]],
            "study_plan": [w.model_dump() for w in response_payload["study_plan"]],
            "intent": response_payload["intent"]
        }
        
        # Persist FULL response text part to chat history
        self._persist_assistant_response(db, session_uuid, response_payload["text"], current_state, db_session)

        # Yield the full dict payload (chat.py will handle merging)
        yield final_payload


    def _persist_assistant_response(self, db, session_uuid, content, current_state, db_session):
        try:
            assistant_msg = ChatMessage(session_id=session_uuid, role="assistant", content=content)
            db.add(assistant_msg)
            db_session.state = current_state.model_dump()
            db.add(db_session)
            db.commit()
        except Exception as e:
            logger.exception(f"Failed to persist assistant/state: {e}")
            db.rollback()

    def _render_recommendation(self, response) -> dict:
        """
        Render the full response payload for the frontend.
        Returns dict with text, courses, and study_plan.
        """
        msg = (response.assistant_message or "").strip()

        # Fallback safety
        if not msg:
            if response.language == "ar":
                msg = "تمام 👍 الـ Roadmap دي جاهزة ليك."
            else:
                msg = "Alright 👍 let's continue with this Roadmap."

        # Safety: If NO courses, do not ask follow-up questions about "these courses"
        if not response.courses:
            response.follow_up_question = None

        # Follow-up question appended if not already in msg
        if response.follow_up_question and response.follow_up_question not in msg:
            if msg:
                msg = f"{msg}\n\n{response.follow_up_question}"
            else:
                msg = response.follow_up_question

        return {
            "text": msg,
            "courses": response.courses or [],
            "study_plan": response.study_plan or [],
            "intent": response.intent,
            "follow_up": response.follow_up_question
        }


    def _is_confirmation(self, text: str) -> bool:
        t = (text or "").lower().strip()
        return t in ["yes", "y", "ok", "okay", "sure", "agreed", "correct", "ah", "tamam", "mashy", "aywa", "naam", "akid", "tab3an"]

    def _is_negation(self, text: str) -> bool:
         t = (text or "").lower().strip()
         return t in ["no", "n", "nope", "nah", "la", "laa", "cancel"]
    
    def _is_refinement(self, text: str) -> bool:
        return len(text.split()) < 5
    
    def _is_study_plan_request(self, text: str) -> bool:
        """Detect if user is asking for a study plan."""
        t = (text or "").lower().strip()
        arabic_keywords = ["خطة", "عاوز خطة", "عايز خطة", "جدول", "خطة دراسة"]
        english_keywords = ["plan", "study plan", "schedule", "roadmap", "learning plan"]
        return any(k in t for k in arabic_keywords + english_keywords)

    def _select_rag_query(self, state, message, extracted, is_refinement):
        if is_refinement and state.active_topic:
            return f"{state.active_topic} {message}"
        return message

    def _is_out_of_scope(self, message: str) -> bool:
        keywords = ["cooking", "recipe", "politics", "religion", "stock market", "dating", "movie"]
        msg_lower = (message or "").lower()
        return any(k in msg_lower for k in keywords)
    
    def _update_state_from_message(self, message: str, state: ChatSessionState) -> None:
        """
        Extract and update state from user message using normalize_text.
        """
        result = normalize_text(message, LEARNING_MAPPING)
        
        # PATH has absolute priority
        if result["type"] == "path":
            state.active_path = result["value"]
            logger.info(f"Path locked: {result['value']}")
        
        # CATEGORY detection
        elif result["type"] == "category":
            if not state.active_path: # Don't overwrite path with category
                state.active_category = result["value"]
                logger.info(f"Category detected: {result['value']}")

        # LEVEL updates anytime
        elif result["type"] == "level":
            state.user_level = result["value"]
            logger.info(f"Level set: {result['value']}")
        
        # Check for study plan agreement if in recommendation stage
        if state.stage == "recommend_courses":
            if self._is_confirmation(message):
                state.want_plan = "yes"
            elif self._is_negation(message):
                state.want_plan = "no"

