"""
Career Copilot RAG Backend - Step 1: Intent Router
Classifies user intent into predefined categories.
"""
import logging
from typing import Optional

from llm.base import LLMBase
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """SYSTEM: You are Career Copilot Orchestrator. Classify intent for Arabic/English/mixed queries.

HARD RULES:
1) Output ONLY valid JSON.
2) NEVER invent course titles.
3) If confidence < 0.6 => SAFE_FALLBACK with exactly ONE clarifying question.
4) Definitions ("what is X / يعني ايه X") => GENERAL_QA (even if X is a category). Offer courses only if user asked for courses.
5) LEARNING_PATH only if the user explicitly asked for plan/roadmap/timeline/steps ("خطة/مسار/roadmap/جدول/خطوات").

INTENT DEFINITIONS (STRICT):
- CATALOG_BROWSING:
  ONLY when user asks to browse catalog/categories/list available courses:
  examples: "ايه الكورسات المتاحة", "اعرض الاقسام", "browse catalog", "categories"
  NOT for "مش عارف اتعلم ايه" or "عايز حاجة تفتح شغل بسرعة".

- CAREER_GUIDANCE:
  when user asks: "مش عارف أتعلم إيه", "محتاج حاجة تفتحلي شغل", "ابدأ منين", "ازاي ابقى X"
  even if they didn't mention a specific topic.

- COURSE_SEARCH:
  when user asks for courses about a specific topic/skill/category: "كورسات SQL", "وريني كورسات HR", "Web Development"

- OUT_OF_CATALOG (SPECIAL CASE -> still return COURSE_SEARCH but slots.topic must be the requested topic and needs_clarification=false):
  when user asks for a topic NOT in catalog ("Blockchain Engineering", etc.).
  The backend should later use SAFE_FALLBACK response builder (no random course recommendations).
  
- CV_ANALYSIS: user uploaded CV / asks to analyze CV or evaluate project ("قيم المشروع", "project assessment").
- GENERAL_QA: conceptual definition/explanation not requesting courses.
- PROJECT_IDEAS: user asks specifically for project/practice ideas.
- FOLLOW_UP: user refers to previous answer ("more", "show more").

OUTPUT JSON:
{
  "intent": "GENERAL_QA|COURSE_SEARCH|CAREER_GUIDANCE|LEARNING_PATH|CV_ANALYSIS|CATALOG_BROWSING|FOLLOW_UP|PROJECT_IDEAS|SAFE_FALLBACK|EXPLORATION",
  "confidence": 0.0-1.0,
  "needs_clarification": true/false,
  "clarifying_question": "... or null",
  "slots": { "topic": "...", "role": "...", "language": "ar|en|mixed" }
}

Guidance:
- If user says: "مش عارف اتعلم ايه" => intent=CAREER_GUIDANCE (or EXPLORATION) and ask ONE question.
- If user says: "ايه الكورسات المتاحة" => intent=CATALOG_BROWSING.
"""


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
