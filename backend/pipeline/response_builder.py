"""
Career Copilot RAG Backend - Step 6: Response Builder (Production Lock)
Ensures all responses adhere to the strict ChatResponse schema.
"""
import logging
import json
from typing import List, Optional, Dict, Any

from llm.base import LLMBase
from models import (
    IntentType, IntentResult, CourseDetail, ChatResponse, 
    SkillValidationResult, SemanticResult, NextAction
)
from utils.lang import is_arabic

logger = logging.getLogger(__name__)

RESPONSE_SYSTEM_PROMPT = """You are Career Copilot, a strict career-learning assistant connected to an internal course catalog.

Core rules:
1) You must NOT hallucinate courses. Any course you show must come from the catalog retrieval results.
2) You must detect when the user is asking for:
   - PROJECT IDEAS (e.g., "افكار مشاريع بايثون", "project ideas", "idea for a python project")
   - COURSE SEARCH (e.g., "رشحلي كورسات بايثون", "عايز كورس بايثون", "show python courses")

3) If the user asks for PROJECT IDEAS:
   - Do NOT run course search as the main action.
   - Provide 8–12 concrete Python project ideas grouped by difficulty (Beginner / Intermediate / Advanced).
   - For each idea: short description + key skills + suggested stretch feature.
   - Only after the ideas, you MAY optionally suggest up to 3 relevant courses IF and only if the user explicitly asks for courses, or if the UI requires showing courses then show "optional learning courses" but never replace the ideas with courses.

4) If the user asks for a STUDY PLAN timeline change as a follow-up (e.g., "اعملي خطة 3 اسابيع"):
   - Continue the last topic, do not change domain.

5) Out-of-scope topics (e.g., cooking/طبخ):
   - Respond with OUT_OF_SCOPE and zero courses. No random fallback.

6) Always mirror the user's language (Arabic → Arabic).
7) CRITICAL RULE: Domain names (المجالات) and Skills (المهارات) must ALWAYS be written in English, even when the rest of the sentence is in Arabic.

Output must always follow this JSON schema:
{
  "intent": "...",
  "answer": "...",
  "projects": [
    { "title": "...", "level": "Beginner|Intermediate|Advanced", "description": "...", "skills": ["..."], "stretch": "..." }
  ],
  "courses": [
    { "title": "...", "level": "...", "instructor": "...", "category": "..." }
  ],
  "next_actions": [
    { "text": "...", "type": "follow_up|course_search|catalog_browse|retry|open_question", "payload": {} }
  ]
}

Important:
- For PROJECT_IDEAS intent, "projects" must be non-empty.
- For COURSE_SEARCH intent, "courses" may be non-empty.
- Do not return courses only when intent is PROJECT_IDEAS.
"""

class ResponseBuilder:
    def __init__(self, llm: LLMBase):
        self.llm = llm

    async def build(
        self,
        intent_result: IntentResult,
        courses: List[CourseDetail],
        skill_result: SkillValidationResult,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        semantic_result: Optional[SemanticResult] = None
    ) -> ChatResponse:
        """
        Builds a ChatResponse following the strict production schema.
        """
        context = context or {}
        from data_loader import data_loader
        
        # 1. Prepare context for LLM
        courses_summary = [
            {"id": str(c.course_id), "title": c.title, "category": c.category, "level": c.level}
            for c in courses[:5]
        ]
        
        prompt = f"""
        User Message: "{user_message}"
        Detected Intent: {intent_result.intent.value if hasattr(intent_result.intent, 'value') else intent_result.intent}
        Relevant Courses: {json.dumps(courses_summary)}
        Last Topic: {context.get("last_topic")}
        """

        try:
            # 1.5 Deterministic OUT_OF_SCOPE (Production Lock)
            if intent_result.intent == IntentType.OUT_OF_SCOPE:
                topic = intent_result.topic or "المجال ده"
                is_ar = is_arabic(user_message)
                answer = f"آسف 🙂 الكتالوج عندي متخصص في التطوير المهني والتقني فقط، ومفيش كورسات عن ({topic}) متاحة حالياً." if is_ar else f"Sorry 🙂 my catalog is specialized in professional and technical development only, and there are no courses about ({topic}) available at the moment."
                return ChatResponse(
                    intent=IntentType.OUT_OF_SCOPE,
                    answer=answer,
                    courses=[],
                    categories=[],
                    next_actions=[
                        NextAction(
                            text="عرض كل المجالات" if is_ar else "Show All Categories",
                            type="catalog_browse"
                        )
                    ],
                    session_state={"last_topic": context.get("last_topic")}
                )

            # 2. LLM Generation
            payload = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=0.0
            )
            
            # 3. Map to ChatResponse
            answer = payload.get("answer", "")
            if not answer:
                 # Fallback if LLM is empty
                 is_ar = is_arabic(user_message)
                 answer = "تفضل، دي أهم النتائج اللي لقيتها ليك." if is_ar else "Here are the best results I found for you."

            # Ensure intent is valid Enum
            res_intent = intent_result.intent
            try:
                llm_intent = payload.get("intent")
                if llm_intent:
                    res_intent = IntentType(llm_intent)
            except Exception:
                pass

            # 3.1 Convert next_actions to structured objects if they are strings
            raw_next_actions = payload.get("next_actions", [])
            next_actions = []
            ALLOWED_ACTIONS = {"follow_up", "course_search", "catalog_browse", "retry", "open_question"}

            for item in raw_next_actions:
                if isinstance(item, str):
                    next_actions.append(NextAction(text=item, type="follow_up"))
                elif isinstance(item, dict):
                    t = item.get("type", "follow_up")
                    if t not in ALLOWED_ACTIONS:
                        t = "follow_up"
                    next_actions.append(NextAction(
                        text=item.get("text", ""),
                        type=t,
                        payload=item.get("payload") or {}
                    ))

            # 3.2 Post-check: If user is lost but response doesn't look like diagnostic questions
            is_ar = is_arabic(user_message)
            lost_triggers = ["تايه", "مش عارف", "محتار", "ساعدني", "lost", "help"]
            msg_lower = (user_message or "").lower()
            is_lost = any(t in msg_lower for t in lost_triggers)
            
            if is_lost and intent_result.intent == IntentType.CAREER_GUIDANCE:
                if "A)" not in answer:
                   logger.warning("Post-check: Response lacks diagnostic options. Injecting Template.")
                   from pipeline.lost_user_flow import LOST_USER_QUESTIONS
                   answer = LOST_USER_QUESTIONS
                   next_actions = [NextAction(text="جاوب بحروف الاختيارات", type="follow_up", payload={"step": "career_questions_v1"})]

            # 3.3 Courses visibility: only show for COURSE_SEARCH or if explicitly requested
            courses_out = courses[:6] if res_intent == IntentType.COURSE_SEARCH else []

            return ChatResponse(
                intent=res_intent,
                answer=answer,
                courses=courses_out,
                projects=payload.get("projects", []),
                categories=payload.get("categories", []),
                next_actions=next_actions,
                session_state={
                    "last_topic": intent_result.topic or context.get("last_topic"),
                    "last_intent": res_intent.value
                }
            )

        except Exception as e:
            logger.error(f"ResponseBuilder Error (Robustness Triggered): {e}", exc_info=True)
            # 4. Strict Error Fallback (Non-breaking experience)
            is_ar = is_arabic(user_message)
            
            # Use contextual topic if possible
            topic = context.get("last_topic") or "هذا المجال"
            
            answer = f"ممكن توضحلي اكتر انت مهتم بإيه في ({topic})؟ حابب ارشحلك كورسات ولا اوضحلك خارطة طريق؟" if is_ar else f"Could you clarify what you're interested in regarding ({topic})? Would you like me to recommend courses or explain a roadmap?"
            
            return ChatResponse(
                intent=intent_result.intent if intent_result else IntentType.UNKNOWN,
                answer=answer,
                courses=[],
                projects=[],
                categories=[],
                next_actions=[
                    NextAction(text="عرض الكورسات" if is_ar else "Show Courses", type="course_search"),
                    NextAction(text="شرح المسار" if is_ar else "Explain Roadmap", type="follow_up")
                ],
                session_state=context
            )
