"""
Career Copilot RAG Backend - Step 1: Intent Router (Stable Production)
- Returns ONLY valid IntentType values.
- Normalizes common LLM variants (e.g., CATALOG_BROWSING -> CATALOG_BROWSE).
- Uses deterministic overrides first to reduce LLM dependence.
"""
import logging
from typing import Optional

from llm.base import LLMBase
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """
You are the Intent Router for Career Copilot RAG.
Return JSON ONLY (no markdown, no extra text).

Allowed intents ONLY:
COURSE_SEARCH, CATALOG_BROWSE, CAREER_GUIDANCE, GENERAL_QA, FOLLOW_UP, SAFE_FALLBACK

Schema:
{
  "intent": "COURSE_SEARCH" | "CATALOG_BROWSE" | "CAREER_GUIDANCE" | "GENERAL_QA" | "FOLLOW_UP" | "SAFE_FALLBACK",
  "topic": string|null,
  "role": string|null,
  "confidence": number,
  "needs_courses": boolean,
  "needs_explanation": boolean
}

Rules:
- If the user asks for a study plan/roadmap/how to become X -> CAREER_GUIDANCE (needs_explanation=true)
- If the user asks to show courses or courses for X -> COURSE_SEARCH (needs_courses=true)
- If user asks what categories you have -> CATALOG_BROWSE
- If user message is short confirmation like "ok/ماشي/تمام/yes" -> FOLLOW_UP
- If uncertain -> SAFE_FALLBACK
"""

ALIASES = {
    "CATALOG_BROWSING": "CATALOG_BROWSE",
    "BROWSE_CATALOG": "CATALOG_BROWSE",
    "CATALOG": "CATALOG_BROWSE",
    "AMBIGUOUS": "SAFE_FALLBACK",
    "UNKNOWN": "SAFE_FALLBACK",
    "OTHER": "SAFE_FALLBACK",
    "EXPLORATION": "SAFE_FALLBACK",
}

class IntentRouter:
    def __init__(self, llm: LLMBase):
        self.llm = llm

    def _check_manual_overrides(self, msg: str) -> Optional[IntentResult]:
        m = (msg or "").strip().lower()

        # Follow-up short confirmations
        if m in {"ماشي", "تمام", "اه", "أه", "ايوه", "أيوة", "ok", "okay", "yes", "yep"}:
            return IntentResult(intent=IntentType.FOLLOW_UP, confidence=0.95)

        # Catalog browsing
        if any(k in m for k in ["ايه المجالات", "الأقسام", "الكتالوج", "catalog", "categories", "مجالات عندك", "وريني المجالات"]):
            return IntentResult(intent=IntentType.CATALOG_BROWSE, confidence=0.95)

        # React / frontend
        if "react" in m:
            # plan request => CAREER_GUIDANCE, else COURSE_SEARCH
            if any(k in m for k in ["خطة", "plan", "roadmap", "مسار", "مذاكرة", "اتعلم"]):
                return IntentResult(intent=IntentType.CAREER_GUIDANCE, topic="React", needs_explanation=True, confidence=0.95)
            return IntentResult(intent=IntentType.COURSE_SEARCH, topic="React", needs_courses=True, confidence=0.9)

        # Sales manager role questions
        is_mgr = any(k in m for k in ["مدير", "manager", "lead", "قيادة"])
        is_sales = any(k in m for k in ["مبيعات", "sales", "selling"])
        if is_mgr and is_sales:
            return IntentResult(intent=IntentType.CAREER_GUIDANCE, role="Sales Manager", topic="Sales Management", needs_explanation=True, needs_courses=True, confidence=0.95)

        # "How to become" style
        if any(k in m for k in ["ازاي", "كيف", "how to", "how do i", "how can i", "أطور نفسي", "develop myself"]):
            return IntentResult(intent=IntentType.CAREER_GUIDANCE, needs_explanation=True, confidence=0.75)

        # Course search verbs
        if any(k in m for k in ["كورسات", "courses", "اعرض", "وريني", "show me", "recommend courses"]):
            return IntentResult(intent=IntentType.COURSE_SEARCH, needs_courses=True, confidence=0.7)

        return None

    async def classify(self, user_message: str, context: Optional[str] = None) -> IntentResult:
        override = self._check_manual_overrides(user_message)
        if override:
            return override

        prompt = f'User Message: "{user_message}"'
        if context:
            prompt = f"Previous Context:\n{context}\n\n{prompt}"

        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=INTENT_SYSTEM_PROMPT,
                temperature=0.0,
            )

            intent_str = (response.get("intent") or "SAFE_FALLBACK").strip().upper()
            intent_str = ALIASES.get(intent_str, intent_str)

            try:
                intent_enum = IntentType(intent_str)
            except Exception:
                logger.warning(f"Invalid intent '{intent_str}' -> SAFE_FALLBACK")
                intent_enum = IntentType.SAFE_FALLBACK

            topic = response.get("topic")
            role = response.get("role")
            confidence = float(response.get("confidence", 0.0) or 0.0)
            needs_courses = bool(response.get("needs_courses", False))
            needs_explanation = bool(response.get("needs_explanation", False))

            return IntentResult(
                intent=intent_enum,
                topic=topic,
                role=role,
                confidence=confidence,
                needs_courses=needs_courses,
                needs_explanation=needs_explanation,
            )

        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            return IntentResult(intent=IntentType.SAFE_FALLBACK, confidence=0.0)

    async def route(self, message: str, session_state: dict) -> IntentResult:
        # Build minimal context string (avoid huge tokens)
        last_topic = session_state.get("last_topic")
        last_intent = session_state.get("last_intent")
        ctx = []
        if last_intent: ctx.append(f"last_intent: {last_intent}")
        if last_topic: ctx.append(f"last_topic: {last_topic}")
        context = "\n".join(ctx) if ctx else None

        return await self.classify(message, context=context)
