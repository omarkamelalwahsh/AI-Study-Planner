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

PATCH — Intent Router Disambiguation (CAREER_GUIDANCE vs PROJECT_IDEAS)

A) CAREER_GUIDANCE MUST trigger when the user asks "how to become / be / improve as" a role or skill.
Examples: "ازاي ابقى مدير ناجح؟", "How to become a Product Owner?", "career pathway", "salary for X".
Return CAREER_GUIDANCE.

B) PROJECT_IDEAS ONLY when the user explicitly asks for projects:
Arabic: "افكار مشاريع", "مشروعين", "portfolio projects", "بني مشروع".

C) PATCH — Intent Router for "I want to learn X":
If user says: "عاوز اتعلم / ذاكر / learn / study + <topic>" (e.g., "عاوز اتعلم SQL")
Route to: COURSE_SEARCH (primary). 
NEVER route to CAREER_GUIDANCE for "I want to learn X" unless they ask about the career path specifically.

D) PATCH — LEARNING_PATH must NOT fall into EXPLORATION flow:
- Intent "LEARNING_PATH" triggers: "خطة", "plan", "roadmap", "جدول مذاكرة".
- If user asks for a plan, return LEARNING_PATH. 
- NEVER route to EXPLORATION_FOLLOWUP for plan requests.

CRITICAL HARD OVERRIDES:
1) If intent == PROJECT_IDEAS:
   - Output must include: { "intent": "PROJECT_IDEAS", "confidence": 1.0, "pipeline": "PROJECTS_ONLY" }

2) If intent == LEARNING_PATH:
   - pipeline must be "PLAN_ONLY"

Output JSON schema:
{
  "intent": "COURSE_SEARCH|LEARNING_PATH|CAREER_GUIDANCE|PROJECT_IDEAS|GENERAL_QA|SAFE_FALLBACK",
  "confidence": 0.0-1.0,
  "pipeline": "PROJECTS_ONLY|PLAN_ONLY|COURSE_SEARCH|QA",
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
        """Strict keyword overrides for production determinism (V15)."""
        msg = message.strip().lower()
        
        # V18 FIX 1: EXPLORATION (User doesn't know what to learn - Ask 3 questions)
        exploration_kws = [
            "مش عارف", "مش عارفة", "لا أعرف", "مش متأكد", "محتار", "confused",
            "don't know", "not sure", "help me decide", "أبدأ منين", "ابدأ منين",
            "عايز حاجة تفتحلي شغل", "تفتحلي شغل", "فتح شغل", "فرصة عمل",
            "مش عارف اتعلم", "مش عارف ابدا", "مش عارفة ابدا"
        ]
        if any(kw in msg for kw in exploration_kws):
            return IntentResult(intent=IntentType.EXPLORATION, confidence=1.0, needs_explanation=True)
        
        # 1. CATALOG_BROWSING (Requirement A - explicit catalog requests only)
        catalog_kws = ["ايه الكورسات", "المتاحة", "كتالوج", "browse", "catalog", "categories", "أقسام", "مجالات", "تخصصات", "ايه المتاح"]
        if any(kw in msg for kw in catalog_kws):
            return IntentResult(intent=IntentType.CATALOG_BROWSING, confidence=1.0, needs_explanation=True)

        # 2) Exact Category Recognition (Deterministic)
        # If user mentions a real catalog category, route to COURSE_SEARCH directly.
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

        # 2. Exact Category Recognition (Stop Hallucinations of absence)
        from data_loader import data_loader
        all_cats = [c.lower() for c in data_loader.get_all_categories()]
        for cat in all_cats:
            if cat in msg and len(cat) > 3: # Avoid short matches like 'ai' if too broad
                return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    confidence=1.0,
                    topic=cat,
                    needs_courses=True,
                    needs_explanation=True
                )

        # 3. COMPOUND MANAGER ROLES (Requirement D)
        manager_roles = {
            "مدير مبرمجين": "Engineering Management",
            "مدير تقني": "Engineering Management",
            "مدير ai": "Engineering Management",
            "مدير فريق": "Leadership & Management",
            "team lead": "Leadership & Management",
            "engineering manager": "Engineering Management"
        }
        for kw, role in manager_roles.items():
            if kw in msg:
                return IntentResult(
                    intent=IntentType.CAREER_GUIDANCE,
                    confidence=1.0,
                    role=role,
                    topic=role,
                    needs_courses=True,
                    needs_explanation=True
                )

        # 3. OTHER DETERMINISTIC RULES
        if any(kw in msg for kw in ["خطة", "مسار", "roadmap", "roadmap", "path"]):
            return IntentResult(intent=IntentType.LEARNING_PATH, confidence=1.0, needs_courses=True, needs_explanation=True)
            
        if any(kw in msg for kw in ["سيفي", "cv", "سيرة ذاتية", "قيم المشروع"]):
            return IntentResult(intent=IntentType.CV_ANALYSIS, confidence=1.0)

        if any(kw in msg for kw in ["غيرهم", "كمان", "more", "next", "المزيد"]):
            return IntentResult(intent=IntentType.FOLLOW_UP, confidence=1.0)

        return None
