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
نظامنا يعمل بـ 28 قسم (Category) محددة مسبقاً. مهمتك هي ربط سؤال المستخدم بهذه الأقسام بدقة.

الأقسام المتاحة (Actual Catalog Categories):
[Banking Skills, Business Fundamentals, Career Development, Creativity and Innovation, Customer Service, Data Security, Digital Media, Disaster Management and Preparedness, Entrepreneurship, Ethics and Social Responsibility, Game Design, General, Graphic Design, Health & Wellness, Human Resources, Leadership & Management, Marketing Skills, Mobile Development, Networking, Personal Development, Programming, Project Management, Public Speaking, Sales, Soft Skills, Sustainability, Technology Applications, Web Development]

أهدافك:
1. **استخراج المحاور (Multi-Axis Analysis)**:
   - أي طلب مركب (مثلاً: مدير مبرمجين) يجب تقسيمه لمحاور:
     - محور إداري (Leadership & Management / Project Management / Business Fundamentals)
     - محور تقني (Programming / Web Development / Technology Applications)
2. **Catalog Honesty**:
   - إذا طلب المستخدم مجالاً غير موجود (مثل AI أو Blockchain أو لغة برمجة معينة)، ابحث عن أقرب "Category" عامة له (مثلاً AI -> Technology Applications).
   - إذا كان المجال بعيداً تماماً عن الكتالوج، ضع "is_in_catalog": false وضع اسم المجال في "missing_domain".
3. **الدقة في الاختيار**:
   - اختر الأقسام الأكثر صلة فقط من القائمة أعلاه.

أجب بـ JSON strict:
{
    "primary_domain": "string (The core topic/role, e.g. 'Sales Manager')",
    "axes": [
        {"name": "Management", "categories": ["..."]},
        {"name": "Technical", "categories": ["..."]}
    ],
    "extracted_skills": ["string"],
    "user_level": "Beginner/Intermediate/Advanced",
    "brief_explanation": "شرح دقيق بالعربي للدور ومسؤولياته.",
    "is_in_catalog": true/false,
    "missing_domain": "string if not in catalog, else null",
    "search_axes": ["Exact user topic (e.g. 'Frontend' NOT 'Web Development')", "Then Broad Category"]
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
        """
        from data_loader import data_loader
        
        # Construct dynamic system prompt
        system_prompt = SEMANTIC_SYSTEM_PROMPT
        if previous_topic:
             system_prompt += f"\n\n[CONTEXT] Previous Topic: \"{previous_topic}\".\nIf the user message is vague or a short follow-up, interpret it as a request for \"{previous_topic}\"."

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
            is_in_catalog = response.get("is_in_catalog", True)
            
            # --- V17 RULE 4: Category Honesty Check (Uses normalize_category) ---
            norm_to_display = data_loader.get_normalized_categories()
            msg_norm = data_loader.normalize_category(user_message)
            for cat_norm in norm_to_display:
                if cat_norm in msg_norm:
                    is_in_catalog = True
                    break
            
            return SemanticResult(
                primary_domain=primary,
                secondary_domains=response.get("secondary_domains", []),
                extracted_skills=response.get("extracted_skills", []),
                user_level=response.get("user_level") or intent_result.level,
                preferences=response.get("preferences", {}),
                brief_explanation=response.get("brief_explanation"),
                axes=response.get("axes", []),
                is_in_catalog=is_in_catalog,
                missing_domain=response.get("missing_domain") if not is_in_catalog else None,
                search_axes=list(dict.fromkeys([primary] + [
                    str(x) for x in response.get("search_axes", []) 
                    if x and isinstance(x, (str, int, float))
                ])),
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
