"""
Career Copilot RAG Backend - Step 1: Intent Router
Classifies user intent into predefined categories.
"""
import logging
from typing import Optional

from llm.base import LLMBase
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """SYSTEM: Career Copilot — Intent Router (Hard Rules)

Output exactly one intent from:
EXPLORATION, EXPLORATION_FOLLOWUP, CATALOG_BROWSING, COURSE_SEARCH, LEARNING_PATH, CAREER_GUIDANCE, FOLLOW_UP, GENERAL_QA, SAFE_FALLBACK

PATCH — Intent Router Disambiguation (CAREER_GUIDANCE vs PROJECT_IDEAS)

A) CAREER_GUIDANCE MUST trigger when the user asks "how to become / be / improve as" a role or skill.
Examples: "ازاي ابقى مدير ناجح؟", "How to become a Product Owner?", "career pathway", "salary for X".

B) COURSE_SEARCH (Primary):
If user says: "عاوز اتعلم / ذاكر / learn / study + <topic>" (e.g., "عاوز اتعلم SQL") or "رشحلي كورسات".

C) LEARNING_PATH:
- Intent "LEARNING_PATH" triggers: "خطة", "plan", "roadmap", "جدول مذاكرة".

D) EXPLORATION:
- Triggers when user is unsure: "مش عارف", "تايه", "محتار", "ساعدني", "مش عارف اختار", "I don't know", "help me choose".

Output JSON schema:
{
  "intent": "EXPLORATION|EXPLORATION_FOLLOWUP|CATALOG_BROWSING|COURSE_SEARCH|LEARNING_PATH|CAREER_GUIDANCE|FOLLOW_UP|GENERAL_QA|SAFE_FALLBACK",
  "confidence": 0.0-1.0,
  "reason": "short",
  "slots": {"topic": "Extract EXACT user topic", "role": "...", "level": "..."}
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
        """Strict keyword overrides for production determinism (Unified Prompt v1)."""
        msg = message.strip().lower()
        
        # EXPLORATION (User unsure)
        exploration_kws = [
            "مش عارف", "تايه", "محتار", "ساعدني", "مش عارف اختار",
            "I don't know", "help me choose", "أبدأ منين", "ابدأ منين"
        ]
        if any(kw in msg for kw in exploration_kws):
            return IntentResult(intent=IntentType.EXPLORATION, confidence=1.0, needs_explanation=True)
        
        # CATALOG_BROWSING
        catalog_kws = ["ايه الكورسات", "المتاحة", "كتالوج", "browse", "catalog", "categories", "أقسام", "مجالات", "تخصصات", "ايه المتاح"]
        if any(kw in msg for kw in catalog_kws):
            return IntentResult(intent=IntentType.CATALOG_BROWSING, confidence=1.0, needs_explanation=True)

        # Exact Category Recognition -> COURSE_SEARCH
        from data_loader import data_loader
        all_cats = [c.lower() for c in data_loader.get_all_categories()]
        for cat in all_cats:
            if cat in msg and len(cat) > 3:
                return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    confidence=1.0,
                    topic=cat,
                    needs_courses=True,
                    needs_explanation=True
                )

        # Manager Roles -> CAREER_GUIDANCE
        if any(kw in msg for kw in ["مدير", "manager", "team lead", "engineering manager"]):
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE,
                confidence=1.0,
                needs_courses=True,
                needs_explanation=True
            )

        # LEARNING_PATH
        if any(kw in msg for kw in ["خطة", "مسار", "roadmap", "path", "plan"]):
            return IntentResult(intent=IntentType.LEARNING_PATH, confidence=1.0, needs_courses=True, needs_explanation=True)
            
        # FOLLOW_UP
        if any(kw in msg for kw in ["غيرهم", "كمان", "more", "next", "المزيد"]):
            return IntentResult(intent=IntentType.FOLLOW_UP, confidence=1.0)

        return None
