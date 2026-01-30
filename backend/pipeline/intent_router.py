"""
Career Copilot RAG Backend - Step 1: Intent Router
Classifies user intent into predefined categories.
"""
import logging
from typing import Optional

from llm.base import LLMBase
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """SYSTEM — Intent Router (Career Copilot)

You are a strict intent classifier for a production RAG chatbot.
Your ONLY job: return a JSON object with:
{
  "intent": "...",
  "confidence": 0.0-1.0,
  "needs_clarification": true/false,
  "clarifying_question": "..." | null,
  "slots": { ... }
}

Do NOT answer the user. Do NOT list courses. Do NOT explain anything.
Do NOT include any keys beyond the schema above.

AVAILABLE INTENTS (choose exactly one):
- CATALOG_BROWSING: user asks what courses exist, categories, "إيه الكورسات المتاحة؟", "ايه المجالات؟", "what courses do you have?"
- COURSE_SEARCH: user asks for courses about a topic/skill ("عاوز كورس بايثون", "learn excel", "كورسات data analysis")
- COURSE_DETAILS: user asks details about a specific course already mentioned ("تفاصيل", "عرض المزيد", "ايه هو الكورس ده؟")
- CAREER_GUIDANCE: user asks how to become a role/path ("ازاي ابقى مدير مبيعات", "how to become content creator")
- PROJECT_IDEAS: user asks for project ideas ("افكار مشاريع", "project ideas")
- LEARNING_PATH: user asks for a time-based plan ("خطة 3 اسابيع ساعتين يوميا", "study plan")
- CV_ANALYSIS: user uploads CV file/image or asks to analyze CV/level
- ATS_CHECK: user asks specifically about ATS compatibility/scoring AND provided file/image
- GENERAL_QA: conceptual definition/explanation not requesting courses ("ايه هي بايثون؟", "يعني ايه data analysis؟")
- FOLLOW_UP: short follow-up that depends on session context ("كمان", "غيرها", "ايه هي؟")

RULES:
1) If message is "إيه هي الكورسات المتاحة؟" or similar → intent MUST be CATALOG_BROWSING (confidence >= 0.95).
2) If message contains "خطة" + timeframe (weeks/hours/day) → LEARNING_PATH.
3) If message asks "افكار مشاريع" → PROJECT_IDEAS.
4) If message is a job/role question starting with "ازاي ابقى" / "how to become" → CAREER_GUIDANCE.
5) If message is "ايه هي X" / "what is X" without asking for courses → GENERAL_QA.
6) If message is ambiguous AND could be COURSE_SEARCH vs CAREER_GUIDANCE, prefer asking ONE clarifying question via fields.
7) FOLLOW_UP only if the message is short AND clearly refers to previous output.

Slots:
- "topic": extracted topic (e.g., python, excel, data analysis)
- "role": extracted role (e.g., sales manager)
- "hours_per_day", "weeks", "level" when available
- "language": "ar" or "en" based on user message

Return JSON only."""


class IntentRouter:
    """Step 1: Classify user intent."""
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def classify(self, user_message: str, context: Optional[str] = None) -> IntentResult:
        """
        Classify the user's intent from their message.
        """
        # Manual Overrides for better responsiveness and accuracy
        override_result = self._check_manual_overrides(user_message)
        if override_result:
            logger.info(f"Manual override intent: {override_result.intent.value}")
            return override_result
            
        prompt = f"User Message: \"{user_message}\""
        
        if context:
            prompt = f"Previous Context:\n{context}\n\n{prompt}"
        
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=INTENT_SYSTEM_PROMPT,
                temperature=0.0,  # Zero temp for strict classification
            )
            
            intent_str = response.get("intent", "AMBIGUOUS")
            confidence = response.get("confidence", 0.0)
            slots = response.get("slots", {})
            
            # V7 Context Persistence: Short specialization answers to clarifying questions
            # If msg < 5 words and intent is ambiguous/follow-up, check if context has a strong previous intent
            if (intent_str in ["AMBIGUOUS", "FOLLOW_UP"]) and context and len(user_message.split()) < 5:
                if "LEARNING_PATH" in context:
                    intent_str = "LEARNING_PATH"
                    confidence = 0.95
                elif "CAREER_GUIDANCE" in context:
                    intent_str = "CAREER_GUIDANCE"
                    confidence = 0.95

            # Validate intent type
            try:
                intent = IntentType(intent_str)
            except ValueError:
                logger.warning(f"Unknown intent type: {intent_str}, defaulting to GENRAL_QA or AMBIGUOUS")
                intent = IntentType.AMBIGUOUS
            
            return IntentResult(
                intent=intent,
                confidence=confidence,
                slots=slots,
                role=slots.get("role"),
                level=slots.get("level"),
                specific_course=slots.get("topic") if intent == IntentType.COURSE_DETAILS else None,
                clarification_needed=response.get("needs_clarification", False),
                clarification_question=response.get("clarifying_question"),
                # Map slots to V5 flags if needed
                needs_courses=(intent in [IntentType.COURSE_SEARCH, IntentType.CATALOG_BROWSING, IntentType.LEARNING_PATH, IntentType.CAREER_GUIDANCE]),
                needs_explanation=(intent in [IntentType.CAREER_GUIDANCE, IntentType.GENERAL_QA, IntentType.CONCEPT_EXPLAIN, IntentType.LEARNING_PATH])
            )
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return IntentResult(
                intent=IntentType.AMBIGUOUS,
                clarification_needed=True,
                clarification_question="عذراً، لم أفهم طلبك. هل يمكنك توضيح ما تبحث عنه؟"
            )

    def _check_manual_overrides(self, message: str) -> Optional[IntentResult]:
        """Check for strict keyword overrides for specific intents (Nuclear Rule 1)."""
        msg_lower = message.strip().lower()
        
        # 0. COURSE_SEARCH Hard Override for explicit course requests (User Fix 1)
        # "عاوز كورس بايثون" -> Must be COURSE_SEARCH, never generic explanation
        course_keywords = ["كورسات", "كورس", "courses", "course", "learn"]
        if any(kw in msg_lower for kw in course_keywords):
            # Check if it's not just "what are courses?" (Catalog browsing handled below)
            # If it has a specific topic (length > ~15 chars usually or contains specific words), assume search
            # But let's trust the user rule: if "course" + topic found -> Search
            # Minimal heuristics: if explicitly asking for courses of X
            pass # Let logic below handle specific phrase matches if needed, or enforce here
            
            # User Rule: "If user asks for 'كورسات' or 'course(s)' about a topic... intent MUST be COURSE_SEARCH"
            # We need to detect "about a topic". Heuristic: message length? Words > 2?
            # Let's check if it strictly fits the "browse" intent first. If not, and has "course", it's likely search.
        
        # 1. CATALOG_BROWSING Hard Override (Scope Guard Rule)
        browse_triggers = {"ايه المجالات الي عندك", "ايه الكورسات اللي عندكم", "المجالات", "الوظائف", "catalog", "categories", "مجالات", "تصفح", "browse", "إيه الكورسات المتاحة"}
        if any(t == msg_lower or msg_lower.startswith(t) or t in msg_lower for t in browse_triggers):
             # Ensure it differentiates from "Python courses"
             if not any(x in msg_lower for x in ["python", "java", "data", "excel", "marketing", "sales"]):
                 return IntentResult(intent=IntentType.CATALOG_BROWSING, needs_explanation=False, needs_courses=True)

        # 2. COURSE_SEARCH Explicit (The fixes)
        # If user says "course" + topic words, force COURSE_SEARCH
        if any(x in msg_lower for x in ["عايز كورس", "عاوز كورس", "محتاج كورس", "ورشحلي كورس", "courses for", "course about"]):
             return IntentResult(intent=IntentType.COURSE_SEARCH, needs_courses=True, confidence=1.0)
        
        # General "courses" keyword check if not captured by browse
        if "كورسات" in msg_lower or "courses" in msg_lower:
             # If not asking "what are available courses" (handled above), it's likely a search
             return IntentResult(intent=IntentType.COURSE_SEARCH, needs_courses=True, confidence=0.99)

        # 3. CAREER_GUIDANCE Hard Override (ازاي ابقى / عايز ابقى)
        guidance_triggers = {
            "ازاي ابقى", "عايز ابقى", "عاوز ابقى", "كيف أصبح", "عايز اشتغل", "أريد أن أصبح",
            "career path", "how to become", " roadmap", "خارطة طريق", "مسار مهني",
            "ازاي ابقى شاطر", "كيف أكون متميزاً"
        }
        for trigger in guidance_triggers:
            if msg_lower.startswith(trigger):
                 role = msg_lower.replace(trigger, "").strip()
                 # Grounding for relevance guard
                 axes = [role] if role else []
                 # User Rule: set slots.offer_courses=true
                 return IntentResult(
                     intent=IntentType.CAREER_GUIDANCE, 
                     role=role, 
                     search_axes=axes, 
                     needs_explanation=True, 
                     needs_courses=True,
                     slots={"offer_courses": True}
                 )

        # 3. Learning Path / Career Guidance (Explicit Keywords)
        # 3. Learning Path / Career Guidance (Explicit Keywords)
        # Fix 1: Hard rules for "Strategy/Roadmap" requests
        roadmap_keywords = ["مسار تعلم", "ابدأ اتعلم", "roadmap", "أتعلم data", "أبدا في data", "learning path", "خطة تعلم", "بداية"]
        soft_skills_keywords = ["communication", "leadership", "time management", "soft skills", "مهارات ناعمة", "تواصل", "قيادة", "problem solving"]
        
        if any(kw in msg_lower for kw in roadmap_keywords) or any(kw in msg_lower for kw in soft_skills_keywords):
             # Prefer LEARNING_PATH for directed roadmaps OR soft skills training
             intent_type = IntentType.LEARNING_PATH
             
             # If strictly soft skills, ensure we set a flag if needed, but Learning Path intent suffices
             # as the Response Builder handles Soft Skills -> Practice Tasks mapping
             
             return IntentResult(
                intent=intent_type,
                confidence=1.0,
                role="" # Placeholder for _extract_potential_role
            )

        # 4. Career Guidance (General)
        career_keywords = ["نصيحة", "إرشاد", "توجيه", "career", "guidance", "تنصحني بإيه", "أعمل إيه"]
        if any(kw in msg_lower for kw in career_keywords):
            return IntentResult(intent=IntentType.CAREER_GUIDANCE, confidence=0.9, needs_explanation=True)

        # 5. Project Ideas
        project_keywords = ["مشروع", "projects", "project", "مشاريع", "أفكار مشاريع", "capstone"]
        opinion_keywords = ["رايك", "opinion", "think", "evaluate", "تفتكر", "تقييمك"]
        if any(kw in msg_lower for kw in project_keywords) and not ("manage" in msg_lower or "مدير" in msg_lower):
             # Guard: If asking for opinion ("ايه رايك في المشروع"), it's likely General Chat/QA, not requesting new ideas
             if any(ok in msg_lower for ok in opinion_keywords):
                 return IntentResult(intent=IntentType.GENERAL_QA, needs_explanation=True)
                 
             return IntentResult(intent=IntentType.PROJECT_IDEAS, confidence=0.9, role=self._extract_potential_role(message) or "General")

        # 6. CV Analysis Trigger (Text-based)
        cv_triggers = ["قيم", "evaluate", "review", "cv", "resume", "سيفي", "السي في", "السيرة الذاتية", "راجع"]
        if any(kw in msg_lower for kw in cv_triggers) and len(message.split()) < 10: # Short command likely
            return IntentResult(intent=IntentType.CV_ANALYSIS, confidence=1.0)
            
        # 4. CONCEPT_EXPLAIN / GENERAL_QA Hard Override
        # User Rule: "what is" -> GENERAL_QA unless asking for courses
        concept_triggers = {
            "يعني ايه", "ايه هو", "ايه هي", "ما هو", "ما هي", "تعريف", "what is", "define"
        }
        for trigger in concept_triggers:
            if msg_lower.startswith(trigger):
                 # Guard: If asking "What is the best course", that's search/advice, not definition
                 if "course" in msg_lower or "كورس" in msg_lower:
                     continue
                 
                 topic = msg_lower.replace(trigger, "").strip()
                 return IntentResult(intent=IntentType.GENERAL_QA, specific_course=topic, search_axes=[topic] if topic else [], needs_explanation=True, needs_courses=False)

        # 5. FOLLOW_UP / CONTEXT REUSE Hard Override (كمان / اصعب)
        # Patch: Specific triggers for "more courses" should map to COURSE_SEARCH
        more_courses_triggers = {
            "في كورسات كمان", "غيرهم", "مزيد من الدورات", "more courses", "كورس كمان", 
            "كورسات تانية", "هل في كورسات كمان", "هل في كورسات غيرها", "مشوفناش كورسات تانية",
            "ليها كورسات", "هل ليها كورسات", "رشحلي كورسات", "في كورسات", "courses", "كورسات"
        }
        if any(t in msg_lower for t in more_courses_triggers):
             return IntentResult(intent=IntentType.COURSE_SEARCH, needs_courses=True)

        follow_up_triggers = {
            "كمان", "اصعب", "أصعب", "مستواه أصعب", "مشاريع أكتر", "عرض المزيد", 
            "غيرهم", "تفاصيل", "more", "next", "المزيد"
        }
        if any(t in msg_lower for t in follow_up_triggers):
            # We return FOLLOW_UP and let the pipeline decide what to reuse
            return IntentResult(intent=IntentType.FOLLOW_UP, needs_courses=True)

        # 6. PROJECT_IDEAS Hard Override
        project_triggers = {"افكار مشاريع", "مشاريع اعملها", "projects", "project ideas", "اعمل مشروع", "build a project"}
        if any(t in msg_lower for t in project_triggers):
            return IntentResult(intent=IntentType.PROJECT_IDEAS)

        # 7. LEARNING_PATH Hard Override
        plan_triggers = {"خطة", "plan", "جدول", "roadmap"}
        if any(t in msg_lower for t in plan_triggers) and any(x in msg_lower for x in ["اسابيع", "ساعات", "يوميا", "weeks", "hours"]):
            return IntentResult(intent=IntentType.LEARNING_PATH, needs_courses=True)

        return None
