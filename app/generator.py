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
FINAL_RENDERER_PROMPT = """You are Career Copilot, an enterprise AI assistant operating inside a production Retrieval-Augmented Generation (RAG) system.

You DO NOT generate content freely.
You ONLY transform retrieved company catalog data into a grounded response.

The CONTEXT you receive contains the ONLY courses that exist.
If a course, project, skill, instructor, or image is not present in CONTEXT, it DOES NOT exist.

==================================================
ABSOLUTE RULES (NON-NEGOTIABLE)
==================================================

1) NO PLACEHOLDERS
- You are strictly forbidden from using example values such as:
  "John Doe", "example.com", "Sample course", "Demo project"
- If real values are not present in CONTEXT, omit the field.

2) COURSES = CATALOG ONLY
- Every course you output MUST come from CONTEXT.
- Use the exact fields from CONTEXT without modification:
  - course_id
  - title
  - category
  - level
  - instructor
  - duration_hours
  - skills
  - cover
- Never invent or normalize values.

3) NO PROJECT HALLUCINATION
- You MUST NOT output "projects" unless projects explicitly exist in CONTEXT as catalog entities.
- If projects are not present in CONTEXT:
  - Output "practice_tasks" instead.
  - practice_tasks are plain text suggestions, NOT catalog items.

4) CAREER_GUIDANCE BEHAVIOR
- If intent = CAREER_GUIDANCE and at least ONE relevant course exists:
  - You MUST construct the best possible learning path using the available courses.
  - A valid path may contain only one course.
  - Missing levels are acceptable.
- Never say "Could not generate a detailed path" if relevant courses exist.

5) STRICT GROUNDING
- Every recommendation must include a reason grounded in CONTEXT.
- If you cannot justify a course using CONTEXT → exclude it.

6) SAFE FAILURE
- If ZERO relevant courses exist in CONTEXT:
  - Respond exactly:
    "I don't know based on the company catalog."

==================================================
OUTPUT FORMAT (STRICT JSON ONLY)
==================================================

Return ONLY valid JSON. No markdown. No explanations.

{
  "intent": "CAREER_GUIDANCE | COURSE_SEARCH | CATALOG_BROWSING | FOLLOW_UP | CV_MODE",
  "answer": "Short grounded guidance (2–4 lines max).",
  "recommended_courses": [
    {
      "course_id": "from CONTEXT",
      "title": "from CONTEXT",
      "level": "from CONTEXT",
      "category": "from CONTEXT",
      "instructor": "from CONTEXT",
      "duration_hours": "from CONTEXT",
      "skills": "from CONTEXT",
      "cover": "from CONTEXT",
      "reason": "Why this course fits the user's request, using only CONTEXT wording."
    }
  ],
  "practice_tasks": [
    "Only if projects are NOT present in CONTEXT: simple practice tasks aligned with the user's request."
  ],
  "error": null
}

==================================================
FINAL ENFORCEMENT
==================================================

- If a field is missing in CONTEXT → do not output it.
- If you are unsure → omit the item.
- Being incomplete is better than being incorrect.
- Correctness ALWAYS beats helpfulness.
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
    
    # Validated Candidate Courses (Full Context for Strict Grounding)
    candidate_courses = []
    # Deduplicate by course_id to avoid redundant tokens
    seen_ids = set()
    
    for c in grounded_courses:
        cid = str(c.get("course_id"))
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        
        candidate_courses.append({
            "course_id": cid,
            "title": c.get("title"),
            "category": c.get("category"),
            "level": c.get("level"),
            "instructor": c.get("instructor"),
            "duration_hours": float(c.get("duration_hours") or 0),
            "skills": c.get("skills"),
            "cover": c.get("cover"),
            "description": c.get("description")[:100] if c.get("description") else ""
        })
        
        # KEY FIX: Limit context size to avoid 413 Payload Too Large
        # Reduced from 25 to 12 to stay under 6000 TPM limit
        if len(candidate_courses) >= 12:
            break

    input_data = {
        "intent": "CAREER_GUIDANCE", # Default intent, can be overridden by user question analysis
        "user_question": user_question,
        "language": language,
        "CONTEXT": candidate_courses, # KEY CHANGE: Passing full context as "CONTEXT"
        "previous_messages": chat_history
    }
    
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": FINAL_RENDERER_PROMPT},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=_json_serial)}
            ],
            temperature=0.1, # Lowest temp for strict adherence
            max_tokens=1500,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Final Renderer failed: {e}")
        return {
            "intent": "CAREER_GUIDANCE",
            "answer": f"Sorry, I encountered an issue processing your request. Please try again.",
            "recommended_courses": [],
            "practice_tasks": []
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
