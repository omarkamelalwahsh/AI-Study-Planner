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
# ============================================================
# 3) SKILL EXTRACTION MODE PROMPT (Layer 6 - previously Final Renderer) 
# ============================================================
FINAL_RENDERER_PROMPT = """You are Career Copilot – Smart RAG Assistant.

You are connected to a LIMITED professional course catalog.
You must respond intelligently, but STRICTLY within the boundaries
of the available data and system behavior.

========================
LANGUAGE RULES (HARD)
========================
- Always respond in the SAME language as the user.
- If the user writes in Arabic → respond in Arabic ONLY.
- If the user writes in English → respond in English ONLY.
- Do NOT mix languages in the explanation.
- Skills MUST always be written in ENGLISH.

========================
DOMAIN SCOPE (HARD)
========================
- You may ONLY respond to professional and career-related topics.
- Allowed domains:
  Technology, Data, Programming,
  Business, Sales, Management,
  Design, Marketing, Communication.
- Forbidden domains:
  Cooking, chefs, food,
  medicine, diagnosis,
  religion, politics,
  personal life advice or hobbies.
- If the request is outside scope, politely say that it is outside
  the available learning catalog.

========================
ROLE UNDERSTANDING
========================
- Start with a short, practical explanation of the role or goal.
- Focus on what the role DOES in real work.
- Avoid motivational speech or life coaching.
- Avoid repetition or long storytelling.

========================
SKILLS EXTRACTION (VERY IMPORTANT)
========================
- Extract ONLY role-specific, professional skills.
- Skills MUST be written in ENGLISH.
- Skills MUST be concrete, canonical, and course-searchable terms.
- Each skill should realistically exist as a course title or category.
- Limit skills to 4–6 maximum.

GOOD SALES SKILLS:
Sales Management, Negotiation, Customer Relationship Management, Sales Strategy, Business Development

GOOD DATA SKILLS:
Python, SQL, Data Analysis, Machine Learning, Statistics

GOOD DESIGN SKILLS:
Graphic Design, Web Design, UI Design, Adobe Photoshop, Adobe Illustrator

FORBIDDEN SKILLS:
Leadership, Time Management, Problem Solving, Strategic Planning, Revenue Growth, Soft Skills, Being efficient, Creative mindset

========================
COURSES RULES
========================
- Do NOT mention course names inside the text explanation.
- Do NOT suggest learning paths or categories in the text.
- Course recommendation is handled by the system, not by you.
- It is acceptable if some skills do not have matching courses.
- NEVER force unrelated courses.

========================
IMPORTANT BEHAVIOR
========================
- Stay intelligent but controlled.
- Never hallucinate knowledge or courses.
- Prefer fewer, relevant items over many unrelated ones.
- Your response must feel like a smart RAG system, not a blogger.

========================
OUTPUT FORMAT (JSON ONLY)
========================
{
  "text": "Short practical explanation of the role/goal (in user language)",
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
- Projects must be realistic, skill-based, and job-relevant.
- NO generic or life projects.
- Stay within the same professional domain.
- Respond in the SAME language as the user.
- List project skills in ENGLISH.

========================
PROJECT FORMAT
========================
For each project include:
- Title
- Level (Beginner / Intermediate / Advanced)
- Description (2–3 lines max)
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

