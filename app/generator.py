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
GUIDANCE_PLANNER_PROMPT = """You are the Career Guidance Planner (Stage 1: Understanding & Guidance).

Input:
- user_question
- router_output (intent, user_goal, target_role, thinking)

Task:
- Provide high-level, actionable career guidance tailored to the user's goal.
- Focus strictly on professional steps, habits, and domain-specific advice.
- You must NEVER mention any course names or specific catalog items here.
- Stage 1 is about conceptual guidance only.

Output JSON only:
{
  "guidance_intro": "Professional 1-2 sentence overview in user's language.",
  "core_areas": [
    {"area": "string", "why_it_matters": "string", "actions": ["list", "of", "actions"] }
  ]
}
"""

# ============================================================
# 2) FINAL RESPONSE RENDERER PROMPT (Layer 6)
# ============================================================
FINAL_RENDERER_PROMPT = """You are the Career Guidance Renderer (Stage 4: Final Rendering).

Input:
- user_question
- guidance_plan (intro + core_areas from Stage 1)
- grounded_courses (courses actually found in catalog)
- coverage_note (optional)
- language

ABSOLUTE RULES:
1) CATALOG IS THE SINGLE SOURCE OF TRUTH: Never invent or hallucinate courses. Suggest ONLY what is in 'grounded_courses'.
2) NO FORCED MAPPING: If 'grounded_courses' is empty, honestly state that no relevant courses exist in the current catalog.
3) HONESTY: If the catalog lacks coverage, provide guidance conceptually but DO NOT fill gaps with unrelated content.
4) NO FAILURE LEAKAGE: Never say "No courses found for X". Handle gaps gracefully.
5) DUAL ROLE (COURSE + SKILL): If only ONE relevant course exists, present it once and expand on why it's valuable.

Presentation:
- Mirror user language.
- Guidance Intro + top bullets first.
- Group courses by category.
- If too many courses (>10), paginate/truncate with "More available".

OUTPUT: User-facing text only.
"""

from datetime import datetime

def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def generate_guidance_plan(
    user_question: str,
    router_output: Any
) -> Dict[str, Any]:
    """Layer 2: Generate high-level guidance plan (no courses)."""
    client = Groq(api_key=settings.groq_api_key)
    
    # Prepare input for LLM
    input_data = {
        "user_question": user_question,
        "router_output": {
            "intent": router_output.intent,
            "user_goal": router_output.user_goal,
            "target_role": router_output.target_role,
            "language": router_output.user_language,
            "thinking": router_output.thinking
        }
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": GUIDANCE_PLANNER_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.7, # Slightly creative for guidance
            max_tokens=600,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Guidance Planner failed: {e}")
        # Fallback plan
        return {
            "guidance_intro": "Here is a general guide for your career goal.",
            "core_areas": []
        }

def generate_final_response(
    user_question: str,
    guidance_plan: Dict,
    grounded_courses: List[Dict],
    language: str,
    coverage_note: str = None
) -> str:
    """Layer 6: Generate final user-facing text."""
    client = Groq(api_key=settings.groq_api_key)
    
    # Clean course data for LLM context (keep only what's needed for the prompt)
    clean_courses = []
    for c in grounded_courses:
        clean_courses.append({
            "title": c.get("title"),
            "level": c.get("level"),
            "instructor": c.get("instructor"),
            "category": c.get("category"),
            "supported_skills": c.get("supported_skills", [])
        })

    input_data = {
        "user_question": user_question,
        "guidance_plan": guidance_plan,
        "grounded_courses": clean_courses,
        "coverage_note": coverage_note,
        "language": language
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": FINAL_RENDERER_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.5,
            max_tokens=1500,
            timeout=settings.groq_timeout_seconds
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Final Renderer failed: {e}")
        return "Sorry, I encountered an error generating your response."

