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
مهمتك:
1. استخراج المجالات والمهارات.
2. توليد "محاور بحث" (Search Axes) وهي كلمات مفتاحية دقيقة للبحث في الكتالوج.
3. التمييز بين الأدوار (مدير vs مبرمج) طبقاً لقواعد V5.

قواعد التحليل:
1. **الدقة (Precision)**:
   - "مدير" = Engineering Management / Team Leadership.
   - "تقني" (Technical) = Implementation / Coding.
   - إذا كان الطلب استكمالاً (Follow-up) لشيء أصعب، يجب أن تعكس الـ search_axes مهارات متقدمة (Advanced).
2. **Search Axes**:
   - إذا كان CATALOG_BROWSING، اخرج قائمة بمجالات البحث العامة المتاحة في الكتالوج.
3. **Brief Explanation**:
   - اشرح الدور من منظور المسؤولية.
   - في حالة CATALOG_BROWSING، اذكر نبذة عن تنوع المجالات وشجع المستخدم على الاختيار.
4. **الدقة التقنية (Technical Accuracy)**:
   - ابحث عن المعنى الصحيح للمصطلح تقنياً. لا تؤلف معلومات خاطئة (مثلاً: الطباعة ثلاثية الأبعاد ليست عن الألوان RGB).
   - إذا لم تكن متأكداً من التعريف، قل "مجال تقني متخصص" مع ذكر الكلمات المفتاحية المتعلقة به.

أجب بـ JSON strict:
{
    "primary_domain": "string (The core topic/role)",
    "secondary_domains": ["string"],
    "extracted_skills": ["string"],
    "user_level": "Beginner/Intermediate/Advanced",
    "brief_explanation": "A high-quality explanation. If CATALOG_BROWSING, list the categories you encourage them to explore.",
    "search_axes": ["Exact keywords to find in catalog"]
}"""


class SemanticLayer:
    """Step 2: Deep semantic understanding of user queries."""
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def analyze(
        self,
        user_message: str,
        intent_result: IntentResult,
        previous_topic: Optional[str] = None
    ) -> SemanticResult:
        """
        Extract semantic information using LLM.
        
        Args:
            user_message: The user's input text
            intent_result: The result from the Intent Router
            previous_topic: The topic of the previous turn (for context)
            
        Returns:
            SemanticResult object
        """
        # Construct dynamic system prompt
        system_prompt = SEMANTIC_SYSTEM_PROMPT
        if previous_topic:
             system_prompt += f"\n\nCONTEXT INFO:\nPrevious Topic: {previous_topic}\nIf user asks a vague follow-up (e.g., 'what skills', 'how to start'), assume they refer to '{previous_topic}'."

        prompt = f"""
User Message: "{user_message}"
Detected Intent: {intent_result.intent.value}
Target Role: {intent_result.role or 'None'}
Previous Context Topic: {previous_topic or 'None'}

Analyze and return JSON.
"""
        
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            
            primary = response.get("primary_domain") or intent_result.role or "General"
            
            return SemanticResult(
                primary_domain=primary,
                secondary_domains=response.get("secondary_domains", []),
                extracted_skills=response.get("extracted_skills", []),
                user_level=response.get("user_level") or intent_result.level,
                preferences=response.get("preferences", {}),
                brief_explanation=response.get("brief_explanation"),
                # V5 Fix: Sanitize axes and include primary domain as first AXIS for better retrieval
                search_axes=list(dict.fromkeys([primary] + [
                    str(x) for x in response.get("search_axes", []) 
                    if x and isinstance(x, (str, int, float))
                ]))
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
