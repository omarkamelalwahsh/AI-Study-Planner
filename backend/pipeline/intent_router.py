"""
Career Copilot RAG Backend - Step 1: Intent Router
Classifies user intent into predefined categories.
"""
import logging
from typing import Optional

from llm.base import LLMBase
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """SYSTEM: Career Copilot — Intent Router (Strict Routing v2)

Output exactly one intent from:
TRACK_START, COURSE_SEARCH, CAREER_GUIDANCE, CV_ANALYSIS, GENERAL_QA, FOLLOW_UP, ERROR

HARD RULES:
1) If user message includes a clear track/topic (e.g., Marketing, Programming, Data Science) AND user is "lost/تايه" or beginner -> TRACK_START.
2) If user message includes a career goal/role (e.g., "مدير عام", "Sales Manager") -> CAREER_GUIDANCE.
3) If user asks for courses or says "عاوز اتعلم <Topic>" -> COURSE_SEARCH.

Output JSON schema:
{
  "intent": "TRACK_START|COURSE_SEARCH|CAREER_GUIDANCE|CV_ANALYSIS|GENERAL_QA|FOLLOW_UP|ERROR",
  "confidence": 0.0-1.0,
  "reason": "short",
  "slots": {"topic": "...", "role": "...", "level": "..."}
}
Return JSON only. No extra text."""


class IntentRouter:
    """Step 1: Classify user intent."""
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def classify(self, user_message: str, context: Optional[str] = None) -> IntentResult:
        """
        Classify the user's intent. (Production V15: Orchestrated with strict rules first).
        """
        # 1. Deterministic Overrides (Fastest Path)
        override_result = self._check_manual_overrides(user_message)
        if override_result:
            return override_result
            
        # 2. LLM Path for complex/ambiguous queries
        prompt = f"User Message: \"{user_message}\""
        if context: prompt = f"Previous Context:\n{context}\n\n{prompt}"
        
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=INTENT_SYSTEM_PROMPT,
                temperature=0.0,
            )
            
            intent_str = response.get("intent", "AMBIGUOUS")
            slots = response.get("slots", {})
            
            # Map slots & Context Persistence
            if (intent_str in ["AMBIGUOUS", "FOLLOW_UP"]) and context and len(user_message.split()) < 5:
                if "LEARNING_PATH" in context: intent_str = "LEARNING_PATH"
                elif "CAREER_GUIDANCE" in context: intent_str = "CAREER_GUIDANCE"

            try:
                intent = IntentType(intent_str)
            except ValueError:
                intent = IntentType.AMBIGUOUS
            
            return IntentResult(
                intent=intent,
                confidence=response.get("confidence", 0.0),
                slots=slots,
                role=slots.get("role"),
                level=slots.get("level"),
                topic=slots.get("topic"),
                search_axes=response.get("search_axes", []),
                needs_courses=(intent in [IntentType.COURSE_SEARCH, IntentType.CATALOG_BROWSING, IntentType.LEARNING_PATH, IntentType.CAREER_GUIDANCE]),
                needs_explanation=(intent in [IntentType.CAREER_GUIDANCE, IntentType.GENERAL_QA, IntentType.LEARNING_PATH])
            )
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return IntentResult(intent=IntentType.AMBIGUOUS, clarification_needed=True)

    async def route(self, message: str, session_state: dict) -> IntentResult:
        """
        Production Hardening: Compatibility alias for route().
        User requests this specific signature for robustness.
        """
        # Pass session state context if available
        context = str(session_state) if session_state else None
        return await self.classify(message, context=context)

    def _check_manual_overrides(self, message: str) -> Optional[IntentResult]:
        """Strict keyword overrides for production determinism (v2)."""
        msg = message.strip().lower()
        
        # 1. Detect Domain/Track (Marketing, Python, Databases, Data Science, Business, Design, Programming)
        from data_loader import data_loader
        all_cats = [c.lower() for c in data_loader.get_all_categories()]
        main_domains = ["programming", "data science", "marketing", "business", "design", "development", "python", "databases"]
        
        detected_domain = None
        for domain in main_domains:
            if domain in msg:
                detected_domain = domain.title()
                break
        
        if not detected_domain:
            for cat in all_cats:
                if cat in msg and len(cat) > 3:
                    detected_domain = cat
                    break

        # 2. Lost / Unsure Keywords
        is_lost = any(kw in msg for kw in ["مش عارف", "تايه", "محتار", "ساعدني", "don't know", "help", "ابدأ منين"])

        # 3. Rule B.1: Track + Lost -> TRACK_START (Override ASK_CATEGORY/EXPLORATION)
        if detected_domain and is_lost:
            return IntentResult(
                intent=IntentType.TRACK_START,
                topic=detected_domain,
                confidence=1.0,
                needs_explanation=True,
                slots={"topic": detected_domain}
            )

        # 4. Rule B.2: Career Goal/Role -> CAREER_GUIDANCE
        roles_kws = ["مدير", "manager", "lead", "head of", "director", "قائد", "رئيس", "senior", "specialist"]
        if any(kw in msg for kw in roles_kws):
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE,
                confidence=1.0,
                needs_courses=True,
                needs_explanation=True,
                slots={"role": msg} # Capture the role from message
            )

        # 5. Rule B.1 (Search Path): Track explicitly mentioned -> COURSE_SEARCH
        # BUT ONLY if not lost (caught above)
        if detected_domain:
            return IntentResult(
                intent=IntentType.COURSE_SEARCH,
                topic=detected_domain,
                confidence=1.0,
                needs_courses=True,
                needs_explanation=True,
                slots={"topic": detected_domain}
            )

        # Default: No override
        return None
