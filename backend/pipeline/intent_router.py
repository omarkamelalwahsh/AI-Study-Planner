"""
Career Copilot RAG Backend - Step 1: Intent Router
Classifies user intent into predefined categories.
"""
import logging
from typing import Optional

from llm.base import LLMBase
from models import IntentType, IntentResult

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """أنت محرك تحليل النوايا (Intent Router) لنظام Career Copilot.
مهمتك هي تحديد نية المستخدم بدقة من قائمة محددة.

يجب عليك اختيار نية واحدة فقط من التالي:
1) COURSE_SEARCH: المستخدم يبحث عن كورس بموضوع أو مهارة (مثال: "عاوز اتعلم بايثون", "Python course")
2) CAREER_GUIDANCE: المستخدم يريد توجيه لوظيفة معينة (مثال: "data analyst", "مبرمج")
3) CATALOG_BROWSING: المستخدم يسأل عما هو متاح بشكل عام (مثال: "ايه الكورسات اللي عندكم؟")
4) PROJECT_IDEAS: المستخدم يطلب أفكار مشاريع (مثال: "افكار مشاريع بايثون")
5) LEARNING_PATH: المستخدم يطلب خطة تعلم محددة بوقت وساعات (مثال: "خطة 3 أسابيع")
6) COURSE_DETAILS: المستخدم يسأل عن تفاصيل كورس محدد بالاسم أو الـ ID
7) FOLLOW_UP: كلمات استكمالية مثل "كمان", "زيدني", "تفاصيل أكتر" تشير لنتائج سابقة
8) CONCEPT_EXPLAIN: المستخدم يسأل عن تعريف أو شرح (مثال: "ايه هو X؟", "يعني ايه X؟")

قواعد هامة:
- "مدير برمجة" = CAREER_GUIDANCE (وظيفة مركبة)
- "بايثون" = COURSE_SEARCH (مهارة)
- إذا كان الطلب غير واضح تماماً، اطلب توضيح واحد فقط.

أجب بـ JSON فقط:
{
    "intent": "INTENT_TYPE",
    "role": "الوظيفة إن وجدت أو null",
    "level": "المستوى (Beginner/Intermediate/Advanced) أو null",
    "specific_course": "اسم الكورس المحدد أو null",
    "clarification_needed": true/false,
    "clarification_question": "سؤال التوضيح إن لزم أو null"
}"""


class IntentRouter:
    """Step 1: Classify user intent."""
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def classify(self, user_message: str, context: Optional[str] = None) -> IntentResult:
        """
        Classify the user's intent from their message.
        
        Args:
            user_message: The user's input message
            context: Optional previous conversation context
            
        Returns:
            IntentResult with classified intent and extracted info
        """
        # Manual Overrides for better responsiveness and accuracy
        override_result = self._check_manual_overrides(user_message)
        if override_result:
            logger.info(f"Manual override intent: {override_result.intent.value}")
            return override_result
            
        prompt = f"رسالة المستخدم:\n\"{user_message}\""
        
        if context:
            prompt = f"السياق السابق:\n{context}\n\n{prompt}"
        
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=INTENT_SYSTEM_PROMPT,
                temperature=0.2,  # Low temperature for consistent classification
            )
            
            intent_str = response.get("intent", "AMBIGUOUS")
            
            # Validate intent type
            try:
                intent = IntentType(intent_str)
            except ValueError:
                logger.warning(f"Unknown intent type: {intent_str}, defaulting to AMBIGUOUS")
                intent = IntentType.AMBIGUOUS
            
            return IntentResult(
                intent=intent,
                role=response.get("role"),
                level=response.get("level"),
                specific_course=response.get("specific_course"),
                clarification_needed=response.get("clarification_needed", False),
                clarification_question=response.get("clarification_question"),
            )
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return IntentResult(
                intent=IntentType.AMBIGUOUS,
                clarification_needed=True,
                clarification_question="عذراً، لم أفهم طلبك. هل يمكنك توضيح ما تبحث عنه؟"
            )

    def _check_manual_overrides(self, message: str) -> Optional[IntentResult]:
        """Check for strict keyword overrides for specific intents."""
        msg_lower = message.strip().lower()
        
        # A) CONCEPT triggers
        concept_triggers = {
            "يعني ايه", "ايه هو", "ايه هي", "ما هو", "ما هي", "what is", "define", "شرح",
            "importance", "فايدة", "هل ينفع", "can i use"
        }
        for trigger in concept_triggers:
            if msg_lower.startswith(trigger):
                 return IntentResult(intent=IntentType.CONCEPT_EXPLAIN)

        # B) PROJECT triggers
        project_triggers = {"افكار مشاريع", "projects", "project ideas", "اعمل مشروع", "build a project"}
        if any(t in msg_lower for t in project_triggers):
            return IntentResult(intent=IntentType.PROJECT_IDEAS)

        # C) PLAN triggers
        plan_triggers = {"خطة", "plan", "اسابيع", "weeks", "ساعات", "hours per day", "جدول"}
        if any(t in msg_lower for t in plan_triggers):
            return IntentResult(intent=IntentType.LEARNING_PATH)

        # D) BROWSE triggers
        browse_triggers = {"ايه الكورسات اللي عندكم", "المجالات", "catalog", "categories", "تصفح", "browse"}
        if any(t in msg_lower for t in browse_triggers):
            return IntentResult(intent=IntentType.CATALOG_BROWSING)

        # E) COURSE SEARCH triggers (Explicit)
        search_triggers = {"عاوز اتعلم", "كورسات", "دورة", "course", "learn", "courses"}
        if any(t in msg_lower for t in search_triggers):
             return IntentResult(intent=IntentType.COURSE_SEARCH)
        
        # F) Follow-up triggers
        follow_up_triggers = {
            "كمان", "هل في كورسات غيرها", "show more", "refine search", "تفاصيل", 
            "more", "next", "المزيد"
        }
        if msg_lower in follow_up_triggers or any(msg_lower.startswith(t) for t in follow_up_triggers):
            return IntentResult(intent=IntentType.FOLLOW_UP)
                
        return None
