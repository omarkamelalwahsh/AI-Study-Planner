"""
skills.py
Module for extracting and translating skills from user input (Role Definition) -> English Skills.
This helps the RAG system find relevant courses even if the user asks in Arabic or describes a role.
"""
import logging
import json
from typing import List
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

HYPOTHESIS_PROMPT = """
Given the user message, do the following:

A) Skill Hypotheses (free reasoning allowed):
- Extract a list of "skill hypotheses" relevant to the user request.
- For each hypothesis, create:
  - skill_label_ar (Arabic)
  - skill_label_en (English)
  - lookup_queries: a list of candidate strings to search in the dataset keys (include variations, synonyms, plural/singular, common phrasing).

B) Output:
Return JSON with:
- user_intent: short label
- hypotheses: list of hypotheses (with lookup_queries)

Rules:
1. **Focus on Technical/Hard Skills** likely to be in a course catalog (e.g. "Python", "Project Management").
2. **Exclude GENERIC Soft Skills** (e.g. "Creativity", "Passion") unless role is HR/Soft Skills.

Input: "{user_input}"

Output Schema:
{
  "user_intent": "string",
  "hypotheses": [
    {
      "skill_label_ar": "string",
      "skill_label_en": "string",
      "lookup_queries": ["string", "string"]
    }
  ]
}
"""

def extract_skill_hypotheses(user_input: str) -> dict:
    """
    Returns dict with 'hypotheses' list containing lookup queries.
    """
    if not user_input or len(user_input.strip()) < 2:
        return {"hypotheses": []}
        
    client = Groq(api_key=settings.groq_api_key)
    
    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": HYPOTHESIS_PROMPT.replace("{user_input}", user_input)},
                {"role": "user", "content": "Generate hypotheses JSON."} 
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        
        content = completion.choices[0].message.content
        data = json.loads(content)
        return data
        
    except Exception as e:
        logger.error(f"[SkillExtraction] Failed: {e}")
        return {"hypotheses": []}

# Simple wrapper for backward compatibility if needed, though we will refactor chat.py
def extract_skills_structured(user_input: str) -> List[str]:
    # Legacy wrapper - just returns EN labels
    data = extract_skill_hypotheses(user_input)
    hyps = data.get("hypotheses", [])
    return [h.get("skill_label_en") for h in hyps if h.get("skill_label_en")]


CAREER_ANALYSIS_PROMPT = """
Analyze the user's career guidance request.

Input: "{user_input}"

Goal:
1. Detect and correct any typos in the role (e.g., "god leader" -> "good leader").
2. Identify the **Target Role** (Corrected).
3. Identify 4-6 **Broad Skill Areas** required for this role.
4. For each area, generate **at least 4 search queries** (English/Arabic synonyms, specific terms, variants).

Output JSON:
{
  "correction": "String showing assumption if typo found (e.g. 'I assume you meant...') or null",
  "target_role": "string",
  "skill_areas": [
    {
      "area_name": "string (Title Case)",
      "search_keywords": ["query1", "query2", "query3", "query4..."]
    }
  ]
}

Rules:
- Areas must be broad enough to map to multiple courses.
- Search keywords must include: exact phrase, common variant, synonym, and a broader phrase.
"""

def analyze_career_request(user_input: str) -> dict:
    """
    Analyzes career request to get Role + Broad Areas + Typo Correction.
    """
    if not user_input or len(user_input.strip()) < 2:
        return {"target_role": "Professional", "skill_areas": []}

    client = Groq(api_key=settings.groq_api_key)
    
    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": CAREER_ANALYSIS_PROMPT.replace("{user_input}", user_input)},
                {"role": "user", "content": "Analyze career request."} 
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        
        content = completion.choices[0].message.content
        data = json.loads(content)
        return data
        
    except Exception as e:
        logger.error(f"[CareerAnalysis] Failed: {e}")
        return {"target_role": "Professional", "skill_areas": []}
