"""
Career Copilot RAG Backend - Step 1: Intent Router (Unified Production)
- Returns ONLY valid IntentType values.
- Merges deterministic overrides with LLM-based classification.
- Single source of truth for routing.
"""
import logging
import json
from typing import Optional, Dict

from llm.base import LLMBase
from models import IntentType, IntentResult, OneQuestion

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are an intent router for Career Copilot.
Return ONLY JSON (no extra text).

Possible intents:
- COURSE_SEARCH
- CATALOG_BROWSE
- CAREER_GUIDANCE
- PROJECT_IDEAS
- FOLLOW_UP
- OUT_OF_SCOPE
- UNKNOWN

Rules:
1) If the user explicitly asks for project ideas, apps, side projects, portfolio projects:
   intent = PROJECT_IDEAS

Keywords (Arabic/English) indicating PROJECT_IDEAS:
"افكار مشاريع", "أفكار مشاريع", "مشروع بايثون", "side project", "portfolio project", "project ideas"

2) If the user asks for courses:
intent = COURSE_SEARCH
Keywords:
"كورس", "كورسات", "course", "recommend courses", "رشحلي كورسات"

3) If user asks to adjust an existing plan duration (e.g., "3 اسابيع", "اختصر", "قسّمها"):
intent = FOLLOW_UP and followup_type="PLAN_DURATION_CHANGE"

4) If topic is clearly unrelated to career/professional skills catalog (e.g., cooking/طبخ/recipes):
intent = OUT_OF_SCOPE

Return JSON:
{
  "intent": "…",
  "topic": "…",
  "reason": "short reason",
  "followup_type": null
}
"""

class IntentRouter:
    def __init__(self, llm: LLMBase):
        self.llm = llm

    @staticmethod
    def check_explanation_keywords(message: str) -> Optional[IntentResult]:
        """Static check for Explanation/Definition queries."""
        msg_lower = message.lower()
        triggers = [
            "الفرق بين", "يعني ايه", "فايدة", "شرح", "ما هو", "ما هي",
            "what is", "difference between", "benefit of", "explain", "meaning of"
        ]
        
        if any(t in msg_lower for t in triggers):
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE,
                needs_explanation=True,
                needs_courses=False,
                confidence=1.0,
                topic="General"
            )
        return None

    def _check_manual_overrides(self, msg: str, session_state: Optional[dict] = None) -> Optional[IntentResult]:
        m = (msg or "").strip().lower()
        session_state = session_state or {}

        # --- PRODUCTION FIX: Follow-up Course Request Override ---
        FOLLOWUP_KEYWORDS = ["كورسات", "courses", "ترشيحات", "رشحلي", "عندك كورس", "في كورسات", "فيه كورسات"]
        if any(k in m for k in FOLLOWUP_KEYWORDS):
            last_topic = session_state.get("last_topic")
            if last_topic:
                logger.info(f"IntentRouter: Follow-up Course Search Triggered for topic: '{last_topic}'")
                return IntentResult(
                    intent=IntentType.COURSE_SEARCH,
                    topic=last_topic,
                    reason="Follow-up course request based on session history",
                    needs_courses=True,
                    confidence=1.0
                )

        # 0. STRICT CATALOG BOUNDARY (Production Fix)
        OUT_OF_SCOPE_TRIGGERS = [
            "طبخ", "cooking", "وصفات", "recipes", "كورة", "كرة", "football", "sports",
            "medicine", "علاج", "دواء", "طب ", "أكلة", "اكلة", "طعام"
        ]
        if any(t in m for t in OUT_OF_SCOPE_TRIGGERS):
            logger.info(f"IntentRouter: Out of Scope Triggered for: '{msg}'")
            return IntentResult(
                intent=IntentType.OUT_OF_SCOPE,
                topic=msg,
                confidence=1.0
            )

        # 0.5 PROJECT IDEAS (Production Fix)
        PROJECT_TRIGGERS = [
            "افكار مشاريع", "أفكار مشاريع", "مشروع بايثون", "side project", "portfolio project", 
            "project ideas", "مشروع ", "أفكار مشروع", "افكار مشروع"
        ]
        if any(t in m for t in PROJECT_TRIGGERS):
            logger.info(f"IntentRouter: Project Ideas Triggered for: '{msg}'")
            return IntentResult(
                intent=IntentType.PROJECT_IDEAS,
                topic=msg.replace("افكار", "").replace("أفكار", "").replace("مشاريع", "").replace("مشروع", "").strip(),
                confidence=1.0
            )

        # 1. Lost User / Confused (RULE: Force CAREER_GUIDANCE)
        LOST_TRIGGERS = [
            "تايه", "مش عارف", "محتار", "ساعدني", "مش عارف أبدأ", 
            "مش عارف اختار", "lost", "confused", "help"
        ]
        if any(t in m for t in LOST_TRIGGERS):
            logger.info(f"IntentRouter: Lost User Triggered for message: '{msg}'")
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE,
                topic="General",
                needs_one_question=True,
                slots={
                   "router_one_question": OneQuestion(
                       question="اختار أكتر مجال مهتم بيه:",
                       choices=["Programming", "Data Science", "Marketing", "Business", "Design"]
                   )
                },
                confidence=0.98
            )

        # 2. Follow-up short confirmations
        FOLLOWUP_TRIGGERS = {
            "ماشي", "تمام", "اه", "أه", "ايوه", "أيوة", "ok", "okay", "yes", "yep", 
            "عاوز الاتنين", "both", "الاثنين", "الإثنين", "الاتنين", "more", "كمان", "غيرهم"
        }
        if m in FOLLOWUP_TRIGGERS or m.startswith("more"):
            return IntentResult(intent=IntentType.FOLLOW_UP, confidence=0.95)

        # Explanation/Benefit keywords
        if any(k in m for k in ["faida", "fayda", "benefit", "what is", "عبارة عن ايه", "فايدة", "ليه اتعلم", "اهمية", "how does"]):
             return IntentResult(intent=IntentType.CAREER_GUIDANCE, needs_explanation=True, needs_courses=False, confidence=0.85)

        # Course search verbs
        if any(k in m for k in ["كورسات", "courses", "اعرض", "وريني", "show me", "recommend courses", "display", "عرض"]):
            return IntentResult(intent=IntentType.COURSE_SEARCH, needs_courses=True, confidence=0.7)

        # Tech Skills (Migrated from main.py)
        # Force CAREER_GUIDANCE for broad tech terms to show roadmap/explanation first
        tech_keywords = [
            "react", "sql", "python", "javascript", "node", "java", "frontend", "backend",
            "بايثون", "رياكت", "سيكوال", "جافا", "فرونت", "باك", "تحليل", "analysis"
        ]
        for tech in tech_keywords:
            if tech in m:
                # Map Arabic keyword to English Topic if needed
                topic_map = {
                    "بايثون": "Python",
                    "رياكت": "React",
                    "سيكوال": "SQL",
                    "جافا": "Java",
                    "جافا سكربت": "JavaScript"
                }
                final_topic = topic_map.get(tech, tech.title())
                return IntentResult(
                    intent=IntentType.CAREER_GUIDANCE,
                    topic=final_topic,
                    needs_explanation=True,
                    needs_courses=False,
                    confidence=1.0
                )

        # 3. Catalog browsing
        if any(k in m for k in ["ايه المجالات", "الأقسام", "الكتالوج", "catalog", "categories", "مجالات عندك", "وريني المجالات"]):
            return IntentResult(intent=IntentType.CATALOG_BROWSE, confidence=0.95)

        # 4. Sales manager role overrides
        is_mgr = any(k in m for k in ["مدير", "manager", "lead", "قيادة"])
        is_sales = any(k in m for k in ["مبيعات", "sales", "selling"])
        if is_mgr and is_sales:
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE, 
                role="Sales Manager", 
                topic="Sales Management", 
                needs_explanation=True, 
                needs_courses=True, 
                confidence=0.95
            )

        # 5. Data Analysis overrides
        da_keywords = ["data analysis", "تحليل بيانات", "analyst", "محلل بيانات", "analysis"]
        if any(k in m for k in da_keywords):
            return IntentResult(
                intent=IntentType.CAREER_GUIDANCE,
                topic="Data Analysis",
                needs_explanation=True,
                needs_courses=True,
                confidence=0.95
            )

        return None

    async def route(self, message: str, session_state: dict) -> IntentResult:
        """
        Main routing logic.
        1. Check Overrides.
        2. Call LLM for Classification.
        3. Map LLM Output to IntentResult.
        """
        # 1. Manual Overrides (Passing session_state for context-aware keywords)
        override = self._check_manual_overrides(message, session_state)
        if override:
            return override

        # 2. Build Context
        last_topic = session_state.get("last_topic")
        last_intent = session_state.get("last_intent")
        last_ask = session_state.get("last_ask")
        
        prompt = f"""
        User Request: "{message}"
        Context (Last Topic): {last_topic}
        Context (Last Intent): {last_intent}
        History (Last Ask): {last_ask}
        """

        try:
            # 3. LLM Classification
            payload = await self.llm.generate_json(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=0.0
            )

            # 4. Map Output
            llm_intent = payload.get("intent", "UNKNOWN")
            topic = payload.get("topic")
            role = payload.get("role")
            
            # Map LLM strings to Enum
            try:
                mapped_intent = IntentType(llm_intent)
            except ValueError:
                mapped_intent = IntentType.UNKNOWN

            # Parse OneQuestion
            one_question = None
            oq_data = payload.get("one_question")
            if oq_data and isinstance(oq_data, dict):
                 q_text = oq_data.get("question")
                 q_opts = oq_data.get("options", [])
                 final_opts = []
                 for opt in q_opts:
                    if isinstance(opt, dict):
                        final_opts.append(opt.get("label", str(opt)))
                    else:
                        final_opts.append(str(opt))
                 
                 if q_text:
                     one_question = OneQuestion(question=q_text, choices=final_opts)

            # Construct Result
            return IntentResult(
                intent=mapped_intent,
                topic=topic,
                role=role,
                confidence=1.0,
                needs_courses=payload.get("needs_courses", False),
                needs_explanation=payload.get("needs_explanation") or (llm_intent == "EXPLANATION"),
                needs_one_question=True if (one_question or llm_intent == "LOST_USER") else False,
                slots={"router_one_question": one_question} if one_question else {}
            )

        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            return IntentResult(intent=IntentType.UNKNOWN, confidence=0.0)

