"""
Generator module for creating user-facing responses using Groq LLM.
Implements Layer 2 (Planner) and Layer 6 (Renderer) of the 7-step pipeline.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from groq import Groq
from app.config import settings
from app.system_state import build_catalog_context

logger = logging.getLogger(__name__)

# ============================================================
# 1) GUIDANCE PLANNER PROMPT (Layer 2)
# ============================================================
GUIDANCE_PLANNER_PROMPT = """You are the Guidance Planner. 
Your goal is to provide conceptual career advice without mentioning specific courses.

Task:
- Write a concise plan (3-5 bullets) to reach the user's goal.
- Focus on professional steps, habits, and domain-specific advice.
- Do NOT mention any course names or catalog availability.
- Mirror the user's language.

Output JSON only:
{
  "guidance_intro": "Professional 1-2 sentence overview.",
  "core_areas": [
    {"area": "string", "why_it_matters": "string", "actions": ["list", "of", "actions"] }
  ]
}
"""

# ============================================================
# 2) FINAL RESPONSE RENDERER PROMPT (Layer 6)
# ============================================================
# ============================================================
# 3) SKILL EXTRACTION MODE PROMPT (Layer 6 - previously Final Renderer) 
# ============================================================
FINAL_RENDERER_PROMPT = """You are Career Copilot – Skill Extraction Mode.

Your ONLY responsibility:
1) Provide a short, practical explanation of the role or goal.
2) Extract the key professional skills required.

========================
STRICT RULES
========================
- Respond in the SAME language as the user.
- If Arabic input → Arabic response.
- Skills MUST be written in ENGLISH ONLY.
- Skills must be concrete, professional, and searchable terms (1–2 words).
- DO NOT recommend courses.
- DO NOT mention course names.
- DO NOT suggest learning paths or categories.
- Avoid soft skills unless the role itself is non-technical.

========================
OUTPUT FORMAT (JSON ONLY)
========================
{
  "text": "شرح مختصر وعملي للدور",
  "skills": ["Skill1", "Skill2", "Skill3"]
}
"""

# ============================================================
# 4) PROJECT IDEAS GENERATOR PROMPT (Layer 7 - New Feature)
# ============================================================
PROJECT_IDEAS_PROMPT = """You are Career Copilot – Project Ideas Generator.

The user has already received relevant courses.
Your task is to suggest practical project ideas related to the user's original goal.

========================
RULES
========================
- Generate EXACTLY 3 project ideas.
- Projects must be directly related to the user's original goal.
- Use increasing difficulty levels:
  1) Beginner
  2) Intermediate
  3) Advanced
- Projects must be practical and skill-based.
- NO life advice.
- NO generic projects.
- Stay within professional / technical scope.
- Respond in the SAME language as the user.

========================
PROJECT FORMAT
========================
For each project include:
- Title
- Level
- Description (2–3 lines)
- Main skills used (ENGLISH)

========================
OUTPUT FORMAT (JSON ONLY)
========================
{
  "projects": [
    {
      "title": "",
      "level": "Beginner",
      "description": "",
      "skills": []
    },
    {
      "title": "",
      "level": "Intermediate",
      "description": "",
      "skills": []
    },
    {
      "title": "",
      "level": "Advanced",
      "description": "",
      "skills": []
    }
  ]
}
"""

def generate_final_response(
    user_question: str,
    guidance_plan: Dict,
    grounded_courses: List[Dict],
    language: str,
    coverage_note: str = None
) -> Dict[str, Any]:
    """
    Layer 6: Generate final response - NOW Skill Extraction Mode.
    Returns JSON { "text": "...", "skills": [...] }
    """
    client = Groq(api_key=settings.groq_api_key)
    
    # Input data minimal for this mode
    # We still pass courses but the Prompt is told NOT to use them? 
    # Wait, the prompt says "Your ONLY responsibility... DO NOT recommend courses."
    # So we don't strictly need courses in the prompt but we keep signature compatible.
    
    input_data = {
        "user_question": user_question,
        "language": language
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": FINAL_RENDERER_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.3, # Low temp for extraction and structured output
            max_tokens=800,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Skill Extraction Mode failed: {e}")
        return {
            "text": "Sorry, I could not process the request details at this moment.",
            "skills": []
        }

def generate_project_ideas(
    user_question: str,
    language: str
) -> Dict[str, Any]:
    """
    Layer 7: Generate Project Ideas.
    """
    client = Groq(api_key=settings.groq_api_key)
    
    input_data = {
        "user_question": user_question,
        "language": language
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": PROJECT_IDEAS_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.6,
            max_tokens=1000,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Project Generator failed: {e}")
        return {"projects": []}

