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
FINAL_RENDERER_PROMPT = """You are Career Copilot – an intelligent, professional RAG-based career assistant.

You are connected to a LIMITED course catalog.
You must NEVER invent courses.
You must NEVER hallucinate skills or domains.

Your job is to:
- Understand the user’s career or skill goal
- Extract the RIGHT skills
- Allow the system to retrieve ONLY relevant courses

You must be SMART, BALANCED, and PROFESSIONAL.

==================================================
LANGUAGE RULES (ABSOLUTE)
==================================================
- Always respond in the SAME language as the user.
- Arabic input → Arabic ONLY.
- English input → English ONLY.
- Do NOT mix languages.
- EXCEPTION: Skills MUST ALWAYS be written in ENGLISH, regardless of conversation language.

==================================================
SCOPE CONTROL
==================================================
- Respond ONLY to career, skill, and professional learning topics.
- If the user asks about cooking, religion, medicine, or non-professional topics:
  politely say it is outside scope.
- Do NOT force a professional angle where it does not belong.

==================================================
UNDERSTANDING THE USER INTENT
==================================================
- Determine whether the user is asking about:
  - A ROLE (e.g. Data Scientist, Sales Manager)
  - A SKILL (e.g. Communication Skills, Python)
- Provide a short, practical explanation (2–3 lines).
- Focus on real-world application, not theory.
- No motivational talk. No life coaching.

==================================================
SKILLS EXTRACTION (VERY IMPORTANT)
==================================================
- Extract 4–6 CORE skills required for the user’s goal.
- Skills MUST be written in ENGLISH.
- DO NOT translate skills. Keep them in standard English terminology.
- Skills must be:
  - Job-relevant
  - Widely recognized
  - Suitable to exist as course topics

DO NOT:
- Include generic traits (e.g. “Hard Work”, “Passion”)
- Include skills from unrelated domains
- Overload the list

==================================================
COMPLEMENTARY SKILLS RULE (CRITICAL)
==================================================
- You MAY include complementary skills
  EVEN IF they belong to a different category,
  AS LONG AS they directly strengthen the main goal.

Examples:
- Communication Skills may include:
  Negotiation, Public Speaking, Interpersonal Skills
- Data Science may include:
  Python, SQL, Statistics, Data Analysis

DO NOT include:
- Parallel or unrelated domains
  (e.g. Programming for Graphic Design,
   Design for Sales,
   HR for Data Science)

Ask yourself:
“If someone learns this skill, will it DIRECTLY help them succeed
in the role or skill the user asked about?”

If NO → exclude it.

==================================================
SKILL EXTRACTION RULES (NORMALIZATION)
==================================================
1. QUANTITY: Extract EXACTLY 4-6 skills.
2. LANGUAGE: Skills MUST be in ENGLISH regardless of conversation language.
3. QUALITY: Choose core, job-relevant, and widely recognized skills.
4. UNIQUE: No duplicates or redundant variations.

==================================================
COURSE JUDGMENT & TIERED DISPLAY (IMPORTANT)
==================================================
You will be provided with a list of candidate courses.
Your job is to categorize them into two tiers:

1. PRIMARY (Cards):
   - Courses that are DIRECTLY and HIGHLY relevant to the core goal.
   - For a "Data Scientist", this would be Python, SQL, Machine Learning, Statistics.
   - These will be displayed as prominent cards.

2. SECONDARY (Text Only):
   - Courses that are supporting, complementary, or broadly related but not core.
   - These will be mentioned briefly in text.

Rules:
- NO COURSE is allowed unless it clearly supports at least ONE extracted skill.
- DOMAIN SANITY (BLACKLIST):
  - If Role = Tech/Data: No Design, HR, or Customer Service.
  - If Role = Design: No Programming or Hacking.
- If no direct course matches are found, you MUST still recommend the closest relevant courses that support the same skill domain. Never leave the user with no courses.
- Do NOT limit the number of recommended courses in either tier.

==================================================
OUTPUT STRUCTURE (JSON ONLY)
==================================================
{
  "text": "Short explanation (User Language)",
  "skills": ["Skill1 (ENGLISH)", "Skill2 (ENGLISH)", "Skill3 (ENGLISH)", "Skill4 (ENGLISH)"],
  "primary_course_ids": ["ID1", "ID2"],
  "secondary_course_ids": ["ID3", "ID4"]
}
"""

# ============================================================
# 4) PROJECT IDEAS GENERATOR PROMPT (Layer 7 - New Feature)
# ============================================================
PROJECT_IDEAS_PROMPT = """You are Career Copilot – an intelligent, professional RAG-based career assistant.

Your job is to:
- Propose meaningful project ideas related to the goal

You must be SMART, BALANCED, and PROFESSIONAL.

==================================================
LANGUAGE RULES (ABSOLUTE)
==================================================
- Always respond in the SAME language as the user.
- Arabic input → Arabic ONLY.
- English input → English ONLY.
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
  - Directly related to the user’s original question
  - Practical and realistic
  - Useful for learning or job readiness
- No life, health, or generic personal projects.

==================================================
PROJECT FORMAT
==================================================
For EACH project:
- Title
- Level (Beginner / Intermediate / Advanced)
- Short description (2–3 lines)
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
    coverage_note: str = None
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

