"""
skills.py
Module for extracting and translating skills from user input (Role Definition) -> English Skills.
This helps the RAG system find relevant courses even if the user asks in Arabic or describes a role.
"""
import logging
from typing import List
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

SKILL_EXTRACTION_PROMPT = """
You are a career expert system.
The user will give you a "Role" or "Job Title" (potentially in Arabic or English).
Your task is to:
1. Identify the core technical and soft skills required for this role.
2. Translate these skills into concise English keywords that would be found in a course catalog.
3. Return ONLY a single line of space-separated English keywords.

Input: "{user_input}"

Rules:
- Output MUST be English only.
- Output MUST be single string space-separated.
- Limit to top 5-8 most important skills.
- NO explanations, NO intro, NO markdown. Just the keywords.

Example:
Input: "عايز ابقى محاسب شاطر"
Output: Accounting Financial_Analysis Excel Bookkeeping Tax_Law

Input: "Senior Python Developer"
Output: Python Django FastAPI SQL System_Design Docker
"""

def extract_skills_for_role(user_input: str) -> str:
    """
    Uses LLM to map a user's role/goal description to a string of English search keywords.
    """
    if not user_input or len(user_input.strip()) < 3:
        return user_input or ""
        
    client = Groq(api_key=settings.groq_api_key)
    
    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SKILL_EXTRACTION_PROMPT.replace("{user_input}", user_input)},
                {"role": "user", "content": "Extract skills now."} 
            ],
            temperature=0.0,
            max_tokens=100,
            timeout=settings.groq_timeout_seconds
        )
        
        content = completion.choices[0].message.content
        cleaned = content.strip().replace("\n", " ")
        logger.info(f"[SkillExtraction] Input='{user_input}' -> Skills='{cleaned}'")
        return cleaned
        
    except Exception as e:
        logger.error(f"[SkillExtraction] Failed: {e}")
        # Fallback: return original input (will be handled by normal search)
        return user_input
