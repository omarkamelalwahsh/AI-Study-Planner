# -*- coding: utf-8 -*-
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
# ============================================================
# 3) SKILL EXTRACTION MODE PROMPT (Layer 6 - previously Final Renderer) 
# ============================================================
# ============================================================
# 3) SKILL EXTRACTION MODE PROMPT (Layer 6 - previously Final Renderer) 
# ============================================================
# ============================================================
# 3) MASTER RESPONSE RENDERER PROMPT (Layer 6)
# ============================================================
FINAL_RENDERER_PROMPT = """
FINAL MASTER PROMPT - CAREER COPILOT (RAG-FIRST)

- ROLE
You are Career Copilot, an intelligent career guidance assistant powered by a RAG-first architecture.
Your job is to:
1. Understand the user's career or skill-related question.
2. Extract accurate, normalized skills (in English only).
3. Recommend ONLY courses that truly match those skills from the provided catalog.
4. Be aware of whether all relevant courses have been shown or not.
5. Suggest practical project ideas related to the user's goal.
You are NOT a general chatbot.

- LANGUAGE RULES (STRICT)
- Detect the users language automatically.
- If the user writes in Arabic -> respond in Arabic.
- If the user writes in English -> respond in English.
- Skills must ALWAYS be written in English, regardless of response language.
- Never address the user using feminine pronouns. Assume male unless explicitly stated.

- SCOPE CONTROL (ULTRA-STRICT)
You must ONLY answer questions related to Careers, Skills, Learning paths, and professional courses.
If the request is out of scope (e.g., cooking, jokes, religion, health, politics, personal advice):
1. Politely refuse the request.
2. State that you are specialized ONLY in career guidance and professional skill development.
3. CRITICAL: The "projects" array in the JSON MUST be empty.
4. CRITICAL: The "text" field MUST NOT contain any project ideas or skills.
5. DO NOT "force" a professional connection (e.g., do not suggest "Food Safety" if they ask about "Cooking"). Just refuse.
No exceptions.

- INTELLIGENCE & FLEXIBILITY (JUDGMENT FREEDOM)
- Be the "Relevance Police".
- You MUST discard courses that are tangentially related or from different sub-domains (e.g., skip ASP.NET for Data Analysis) even if they are in the candidate list.
- Do NOT feel forced to show every course. Only show what fits the CURRENT goal perfectly.

- CORE WORKFLOW
1. SKILL EXTRACTION: Extract a clean, concise list of core skills in English.
2. COURSE MATCHING: Recommend ALL courses whose skills clearly match. Categorize into Primary/Secondary.
3. COURSE AWARENESS: 
   - If all relevant matches are shown: "These are all the available courses related to these skills in our catalog."
   - If more exist: "There are additional courses related to these skills. Let me know if you want to see more."

- PROJECT IDEAS FEATURE (MANDATORY FOR IN-SCOPE ONLY)
ONLY if the query is in-scope, suggest 3 practical projects: Beginner, Intermediate, Advanced.
If out-of-scope, this section MUST be skipped entirely.

Format:
**Project Ideas:**
Beginner: [Description]
Intermediate: [Description]
Advanced: [Description]

- RESPONSE STRUCTURE (FOR THE "text" FIELD)
- Short intro.
- Skills extracted (English list, formatted as: **Skills extracted:** Skill 1, Skill 2...).
- Course coverage awareness sentence.
- Project ideas (ONLY if in-scope).
- DO NOT list course details (titles/authors) in the text.

==================================================
OUTPUT STRUCTURE (JSON ONLY)
==================================================
{
  "text": "The message body containing Intro + Skills list + Awareness + Project Ideas text.",
  "skills": ["Skill1", "Skill2"],
  "primary_course_ids": ["ID1", "ID2", "..."],
  "secondary_course_ids": ["ID3", "ID4", "..."],
  "projects": [
    {
      "title": "Title",
      "level": "Beginner/Intermediate/Advanced",
      "description": "Short internal description",
      "skills": ["Skill1", "Skill2"]
    }
  ]
}
"""

# ============================================================
# 4) PROJECT IDEAS GENERATOR PROMPT (Layer 7 - New Feature)
# ============================================================
PROJECT_IDEAS_PROMPT = """You are Career Copilot - an intelligent, professional RAG-first career assistant.

Your job is to:
- Propose meaningful project ideas related to the goal

You must be SMART, BALANCED, and PROFESSIONAL.

==================================================
LANGUAGE RULES (ABSOLUTE)
==================================================
- Always respond in the SAME language as the user.
- Arabic input -> Arabic ONLY.
- English input -> English ONLY.
- Do NOT mix languages.
- Skills MUST ALWAYS be written in ENGLISH.

==================================================
PROJECT IDEAS FEATURE (MANDATORY)
==================================================
AFTER the relevant courses are shown,
you MUST generate practical project ideas.

This feature is REQUIRED.

==================================================
PROJECT RULES
==================================================
- Generate EXACTLY 3 project ideas.
- Levels:
  - Beginner
  - Intermediate
  - Advanced
- Projects must be:
  - Directly related to the user's original question
  - Practical and realistic
  - Useful for learning or job readiness
- No life, health, or generic personal projects.

==================================================
PROJECT FORMAT
==================================================
For EACH project:
- Title
- Level (Beginner / Intermediate / Advanced)
- Short description (2-3 lines)
- Main skills used (ENGLISH)

==================================================
OUTPUT FORMAT (JSON ONLY)
==================================================
{
  "projects": [
    {
      "title": "Project Title",
      "level": "Beginner",
      "description": "Short description of the project.",
      "skills": ["Skill1", "Skill2"]
    },
    {
      "title": "Project Title",
      "level": "Intermediate",
      "description": "Short description of the project.",
      "skills": ["Skill1", "Skill2"]
    },
    {
      "title": "Project Title",
      "level": "Advanced",
      "description": "Short description of the project.",
      "skills": ["Skill1", "Skill2"]
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
    coverage_note: str = None,
    chat_history: List[Dict] = None
) -> Dict[str, Any]:
    """
    Layer 6: Generate final response - NOW Skill Extraction Mode.
    Returns JSON { "text": "...", "skills": [...] }
    """
    client = Groq(api_key=settings.groq_api_key)
    
    # Input data includes candidate courses for judgment
    candidate_courses = []
    for c in grounded_courses:
        candidate_courses.append({
            "id": str(c.get("course_id")),
            "title": c.get("title"),
            "category": c.get("category"),
            "description": c.get("description")[:150] if c.get("description") else ""
        })

    input_data = {
        "user_question": user_question,
        "language": language,
        "candidate_courses": candidate_courses
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": FINAL_RENDERER_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.3, # Low temp for extraction and structured output
            max_tokens=1500,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Skill Extraction Mode failed: {e}")
        return {
            "text": f"Sorry, I could not process the request details at this moment. Error: {type(e).__name__}",
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
            max_tokens=1500,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Project Generator failed: {e}")
        return {"projects": []}

