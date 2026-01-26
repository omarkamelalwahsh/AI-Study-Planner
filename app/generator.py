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
from datetime import datetime

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
FINAL_RENDERER_PROMPT = """You operate in ONE mode only.

MODE can be:
- INITIAL
- FOLLOWUP_PROJECTS
- FOLLOWUP_COURSES

========================
MODE BEHAVIOR
========================

IF MODE = INITIAL:
- Provide:
  1) Short professional definition
  2) Extracted skills (English only)
  3) Relevant courses (only if they truly fit)
  4) Practice projects (Beginner -> Advanced)

IF MODE = FOLLOWUP_PROJECTS:
- DO NOT repeat definition
- DO NOT repeat skills
- DO NOT repeat previous projects
- ONLY generate NEW, deeper project ideas
- Stay in the SAME domain

IF MODE = FOLLOWUP_COURSES:
- DO NOT repeat definition
- DO NOT repeat skills
- ONLY list additional relevant courses
- If none exist, say clearly: 
  "These are all the available courses in the catalog for this topic."

========================
INTELLIGENCE RULE
========================
Behave like a senior career mentor.
Never restart unless explicitly asked.

================================
CORE THINKING PRINCIPLES
================================

1) CONCEPTUAL UNDERSTANDING (NOT KEYWORDS)
- Always understand the MAIN CONCEPT behind the user’s question.
- Reason in terms of domains and sub-domains (e.g. Programming -> Mobile -> Android).

2) SOFT RELEVANCE (NOT HARD FILTERING)
- Do NOT hard-block courses by category.
- Evaluate relevance logically.
- Only recommend courses that genuinely SUPPORT the user’s goal.

3) SKILLS-FIRST REASONING
- Always extract clear, professional SKILLS (in English).
- Skills must be real industry skills, not vague traits.
- Courses are recommended ONLY if they clearly support one or more extracted skills.

4) PROJECTS AS INTELLIGENCE SIGNAL
- Projects must match the original concept.
- Respect the user’s level (Beginner / Intermediate / Advanced).
- NEVER repeat the same project if the user asks for more.

5) LEVEL-AWARE RESPONSES
- Infer user level when possible.
- Beginner -> fundamentals & simple projects
- Intermediate -> integration & real-world constraints
- Advanced -> optimization, architecture, scalability

6) HONEST CATALOG USAGE
- Never invent courses.
- If all relevant courses are already shown, say so.
- SPECIAL CASE: If the user asks about "Programming Basics", state: "قريبا هنضيف كورسات لأساسيات البرمجة" after providing the definition and skills.

==================================================
OUTPUT STRUCTURE (JSON ONLY)
==================================================
{
  "text": "The message body following the STRICT structure above.",
  "skills": ["Skill1", "Skill2"],
  "primary_course_ids": ["ID1", "ID2", "..."],
  "secondary_course_ids": [],
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
# 3) PROJECT IDEAS GENERATOR PROMPT (Layer 7 - New Feature)
# ============================================================
PROJECT_IDEAS_PROMPT = """You are a Senior Career Mentor and Practical Learning Designer.

Your task is to generate PRACTICAL PROJECT IDEAS that help the user APPLY the skills related to their goal.

You will be given:
- The user's original goal or question
- The extracted skills
- The user's language (Arabic / English / Mixed)
- Previously generated projects (if any) to avoid duplicates

========================
STRICT RULES (DO NOT BREAK):
========================
1. Generate projects ONLY related to the user's domain and extracted skills.
2. Do NOT introduce unrelated fields or categories.
3. Do NOT repeat any previously generated project ideas.
4. Respect the requested or inferred level:
   - Beginner -> simple, foundational
   - Intermediate -> real-world usage, multiple components
   - Advanced -> architecture, scalability, performance
5. Projects must be PRACTICAL and ACTIONABLE.
6. If the user asks for "more projects", generate NEW ideas only.
7. If no courses exist in the catalog, projects are mandatory.
8. NEVER mention databases, APIs, or systems unless relevant to the domain.
9. NEVER explain theory here — ONLY project ideas.

========================
OUTPUT FORMAT (JSON ONLY):
========================
{
  "projects": [
    {
      "title": "Project Title",
      "level": "Beginner/Intermediate/Advanced",
      "description": "Short description.",
      "skills": ["Skill1", "Skill2"]
    }
  ]
}
"""

def infer_mode(user_question: str) -> str:
    """Infers the response mode based entirely on the user question and context clues."""
    q = (user_question or "").lower().strip()

    followup_project_keywords = [
        "في كمان", "غيرها", "افكار تانية", "more ideas",
        "anything else", "ideas", "مشاريع تانية", "projects", "مشاريع"
    ]

    followup_course_keywords = [
        "كورسات تانية", "courses more", "في كورسات كمان", "courses"
    ]

    # Simple heuristic - can be enhanced
    if any(k in q for k in followup_project_keywords):
        return "FOLLOWUP_PROJECTS"

    if any(k in q for k in followup_course_keywords):
        return "FOLLOWUP_COURSES"

    return "INITIAL"

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
    chat_history: List[Dict[str, Any]] = [],
    has_more_in_catalog: bool = False
) -> Dict[str, Any]:
    """
    Layer 6: Generate final response - NOW Mode Aware.
    """
    client = Groq(api_key=settings.groq_api_key)
    
    mode = infer_mode(user_question)
    
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
        "mode": mode,
        "user_question": user_question,
        "language": language,
        "candidate_courses": candidate_courses,
        "has_more_in_catalog": has_more_in_catalog,
        "previous_messages": chat_history,
        "highlight_note": coverage_note
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
        logger.error(f"Final Renderer failed: {e}")
        return {
            "text": f"Sorry, I could not process the request details at this moment.",
            "skills": [],
            "projects": []
        }

def generate_project_ideas(
    user_question: str,
    language: str,
    extracted_skills: List[str] = [],
    previous_projects: List[Dict[str, Any]] = []
) -> Dict[str, Any]:
    """
    Layer 7: Generate Project Ideas.
    """
    client = Groq(api_key=settings.groq_api_key)
    
    input_data = {
        "user_question": user_question,
        "language": language,
        "skills": extracted_skills,
        "previous_projects": previous_projects
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": PROJECT_IDEAS_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.6,
            max_tokens=1200,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Project Generator failed: {e}")
        return {"projects": []}
