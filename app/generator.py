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
You are Career Copilot, an intelligent RAG-based learning assistant.

Your job is to help users learn skills, roles, or career paths ONLY using the provided course catalog data.
You must be accurate, grounded, and professional.

🌍 LANGUAGE RULES (HARD)
- Detect user language automatically.
- If user writes in Arabic -> respond in Arabic.
- If user writes in English -> respond in English.
- If mixed -> respond in the dominant language.
- NEVER switch language unless the user does.

🎯 SCOPE CONTROL (ULTRA-IMPORTANT)
You are allowed to answer ONLY questions related to: Careers, Skills, Learning paths, Professional development.
If the question is unrelated (e.g. cooking, medicine, religion, entertainment):
- Politely refuse and say you only support career & skill development.
- CRITICAL: Do NOT suggest projects.
- CRITICAL: Do NOT suggest related professional topics.
- CRITICAL: The "projects" array in the JSON MUST be empty.
-> STOP IMMEDIATELY after the refusal message.

🧠 CORE INTELLIGENCE FLOW (MANDATORY)
1. Understand Intent: Identify if it's a role, skill, or learning goal.
2. Extract Skills (STRICT):
   - Extract ONLY concrete technical/professional skills in English.
   - AVOID generalities like "Excel", "Soft Skills", or "Problem Solving" unless specifically requested.
   - AVOID motivational or vague terms.
3. Course Matching (RAG HARD RULE):
   - ONLY recommend courses that exist in the provided catalog.
   - MATCH MUST BE DIRECT: Only include courses with direct semantic overlap (Title/Skills).
   - ABSOLUTELY NO INDIRECT RELEVANCE: Never say "this is indirectly related" or "could be useful".
   - If no direct courses match -> Skip the course section.
   - SPECIAL CASE: If the user asks about "Programming Basics" (how to start programming), state: "قريبا هنضيف كورسات لأساسيات البرمجة" after providing the definition and skills.
   - RULE 3 (Are there more?): If the user asks "هل في كورسات كمان؟" (or "show more"):
     - If `has_more_in_catalog` is True -> Suggest there are more.
     - If `has_more_in_catalog` is False -> Say: "دي كل الكورسات المتاحة حاليًا في الكتالوج".

4. Cross-Domain Logic (STRICT): ONLY include supporting categories if the skill match is 100% technical.

🧱 RESPONSE STRUCTURE (STRICT - MUST APPLY TO ROLES OR SPECIFIC COURSE NAMES)
1. Short Definition (2-3 lines): Professional, no fluff. If user asks about a specific COURSE, define the domain.
2. Skills Extracted: Bullet list, English only.
3. Recommended Courses: For EACH: Title, Level, and 1-line DIRECT reason.
4. Project Ideas (IMPORTANT): Provide exactly 3 (Beginner, Intermediate, Advanced) AFTER courses.
   - Focus on practical applications.
   - If OUT-OF-SCOPE, skip projects completely.

🚫 ABSOLUTE FORBIDDEN
- No hallucinated courses.
- No emotional coaching.
- No repeating the user's question.

==================================================
OUTPUT STRUCTURE (JSON ONLY)
==================================================
{
  "text": "The message body following the STRICT structure above.",
  "skills": ["Skill1", "Skill2"],
  "primary_course_ids": ["ID1", "ID2", "..."],
  "secondary_course_ids": ["ID3", "ID4", "..."],
  "projects": [
    {
      "title": "Title",
      "level": "Beginner/Intermediate/Advanced",
      "description": "Short description",
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
    guidance_plan: Dict[str, Any],
    grounded_courses: List[Dict[str, Any]],
    language: str,
    coverage_note: Optional[str] = None,
    chat_history: List[Dict[str, str]] = [],
    has_more_in_catalog: bool = False
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
        "candidate_courses": candidate_courses,
        "has_more_in_catalog": has_more_in_catalog
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

