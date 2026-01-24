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
FINAL_RENDERER_PROMPT = """You are the Career Guidance Renderer (Final Rendering).

You receive:
- user_question
- guidance_plan
- grounded_courses (already retrieved from catalog)
- coverage_note (optional)
- language

STRICT RULES:
1) Use ONLY grounded_courses. Never invent courses or external resources.
2) Do NOT “justify” irrelevant courses. If a course does not clearly help with the user's goal, exclude it from the response.
3) If grounded_courses is empty after filtering, say the catalog currently has no relevant courses ONCE, then provide conceptual guidance only.
4) Never show internal errors or "No courses found for X".
5) If only one relevant course exists, show it once and list the key areas it supports.

RELEVANCE TEST:
Include a course only if a professional pursuing this goal would reasonably benefit from it.

PRESENTATION:
- Mirror user language.
- Start with guidance (short).
- Then list courses grouped by category.
- It is OK to list many courses as long as all are clearly relevant.
- If too many (>20 total), show first 10 per category and say "يوجد المزيد" / "More available".

Output: user-facing text only.
"""

def _relevance_gate(user_question: str, courses: List[Dict]) -> List[Dict]:
    """Deterministic filter to remove domain-mismatched noise."""
    q = (user_question or "").lower()

    # Lightweight role/domain inference from question
    technical = any(x in q for x in [
        "data scientist", "data science", "machine learning", "ml", "ai",
        "backend", "frontend", "developer", "engineer", "python", "sql",
        "علم البيانات", "ذكاء", "تعلم الآلة", "برمجة", "بايثون", "داتاساينس"
    ])
    manager = any(x in q for x in [
        "manager", "lead", "leadership", "مدير", "قيادة", "إدارة", "تيم", "فريق"
    ])

    # Hard reject lists (high-signal, avoid false positives)
    reject_if_manager = ["mysql", "html", "css", "javascript", "react", "adobe", "after effects", "illustrator", "indesign"]
    reject_if_technical = ["hygiene", "renewable energy", "after effects", "illustrator", "indesign", "graphic design", "social media marketing"]

    filtered = []
    for c in courses:
        title = (c.get("title") or "").lower()
        category = (c.get("category") or "").lower()
        blob = f"{title} {category}"

        # Manager: reject tool-specific technical/design noise
        if manager and any(k in blob for k in reject_if_manager):
            continue

        # Technical role: reject obvious non-tech noise
        if technical and any(k in blob for k in reject_if_technical):
            continue

        filtered.append(c)

    return filtered

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
            "role_type": router_output.role_type,
            "language": router_output.user_language
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
    
    # 1. Deterministic Relevance Gate (Safety Barrier)
    grounded_courses = _relevance_gate(user_question, grounded_courses)
    
    # 2. Clean course data for LLM context
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

