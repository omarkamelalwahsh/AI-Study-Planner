"""
Career Copilot RAG Backend - Step 2: Semantic Understanding Layer
Deep semantic analysis of user queries beyond keywords.
"""
import logging
from typing import Optional, List

from llm.base import LLMBase
from models import IntentResult, SemanticResult

logger = logging.getLogger(__name__)

SEMANTIC_SYSTEM_PROMPT = """أنت محلل دلالي (Semantic Analyzer) لنظام Career Copilot.
مهمتك: استخراج المعنى العميق والمهارات والخدمات المطلوبة بدقة مع ضمان أمان المجالات (Domain Safety).

قواعد التحليل:
1. **أمان المجالات (Domain Safety)**:
   - "بايثون" → يقتصر فقط على Programming (و Data Security إذا كان الكورس تقنياً).
   - لا تخلط مجالات غير مرتبطة (مثل Public Speaking أو Banking) إلا إذا طلبها المستخدم صراحة.
2. **الوظائف المركبة**: 
   - "مدير مبيعات" = Sales + Management + Leadership
   - "محلل بيانات" = Data Analysis + Statistics + SQL + Python
3. **المستوى الضمني**:
   - "أول مرة", "من الصفر" = Beginner
   - "تطوير", "تعمق" = Advanced
4. **تحديد المهارات من Catalog**:
   - استخدم مهارات واقعية موجودة في `skills_catalog_enriched_v2.csv`.

أجب بـ JSON:
{
    "primary_domain": "المجال الرئيسي المستهدف",
    "secondary_domains": ["مجالات مرتبطة تقنياً فقط"],
    "extracted_skills": ["مهارات من الكتالوج مثل python, excel, leadership"],
    "user_level": "Beginner/Intermediate/Advanced",
    "preferences": {
        "language": "ar/en",
        "learning_style": "practical/theoretical"
    }
}"""


class SemanticLayer:
    """Step 2: Deep semantic understanding of user queries."""
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def analyze(
        self,
        user_message: str,
        intent_result: IntentResult,
    ) -> SemanticResult:
        """
        Perform deep semantic analysis on user message.
        
        Args:
            user_message: The user's input message
            intent_result: Classification from intent router
            
        Returns:
            SemanticResult with extracted domains, skills, and preferences
        """
        # Build context from intent result
        context_parts = []
        if intent_result.role:
            context_parts.append(f"الوظيفة المستهدفة: {intent_result.role}")
        if intent_result.level:
            context_parts.append(f"المستوى: {intent_result.level}")
        
        context = "\n".join(context_parts) if context_parts else ""
        
        prompt = f"""رسالة المستخدم: "{user_message}"
نوع الطلب: {intent_result.intent.value}
{context}

حلل الرسالة واستخرج المعنى العميق."""
        
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=SEMANTIC_SYSTEM_PROMPT,
                temperature=0.3,
            )
            
            return SemanticResult(
                primary_domain=response.get("primary_domain"),
                secondary_domains=response.get("secondary_domains", []),
                extracted_skills=response.get("extracted_skills", []),
                user_level=response.get("user_level") or intent_result.level,
                preferences=response.get("preferences", {}),
            )
            
        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            # Return minimal result
            return SemanticResult(
                primary_domain=None,
                secondary_domains=[],
                extracted_skills=[],
                user_level=intent_result.level,
                preferences={},
            )
    
    def _merge_skills(self, *skill_lists: List[str]) -> List[str]:
        """Merge multiple skill lists, removing duplicates."""
        seen = set()
        result = []
        for skills in skill_lists:
            for skill in skills:
                skill_lower = skill.lower().strip()
                if skill_lower and skill_lower not in seen:
                    seen.add(skill_lower)
                    result.append(skill)
        return result
