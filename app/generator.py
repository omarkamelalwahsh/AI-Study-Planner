"""
Generator module for creating user-facing responses using Groq LLM.
Layer 3: Formatting & Guardrails.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional
from app.system_state import build_catalog_context

from groq import Groq

from app.config import settings
from app.router import GroqUnavailableError, ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)

# ============================================================
# 1) SYSTEM PROMPT (The "Soul" & Strict Rules)
# ============================================================
# ============================================================
# 1) SYSTEM PROMPT (Renderer Template)
# ============================================================
SYSTEM_PROMPT = """You are the Career Copilot Response Renderer.

RENDERING RULES (STRICT):
1) Never expose internal failures, matching logic, or empty results.
2) Never show "No courses found".
3) If RENDER_MODE is "single_course_expand" (only 1 course):
   - Render it once.
   - Explicitly list ALL relevant skills/areas it supports (even implicit ones).
   - Explain WHY this course matches the user's goal.
4) If RENDER_MODE is "multi_course_grouped":
   - Group by Category (provided in context).
   - List all courses concisely (Title — Level — Instructor).
   - Use the "Show All" philosophy: don't hide courses if they are relevant.
   - If list is very long (>10), show top 10 and mention "More available...".
5) Keep the response human, confident, and concise.
6) Assume typos silently if meaning is obvious.
7) End with ONE short guidance paragraph (max 3 bullets).
8) Show coverage_note ONCE only if provided.

OUTPUT FORMAT (Markdown Body in JSON):
- **Intro**: Acknowledge the goal concisely (e.g. "To master Python, you need a mix of syntax and logic."). **DO NOT repeat the user's question.**
- **Guidance Section**:
  - Explain the *Skill Areas* required for this role/goal using the provided context.
  - Define *why* these skills are important.
  - **CRITICAL**: Do NOT list specific course titles in this text.
  - Instead, say something like: "I have selected recommended courses for you below that cover these areas in depth."
- **Coverage Note** (Optional, at end):
  - Only if needed, say: "Note: Our catalog coverage is currently limited for some topics."

STRICT JSON OUTPUT SCHEMA:
Return JSON only:
{
  "mode": "CAREER_GUIDANCE|SKILL_ROADMAP|COURSE_SEARCH|COURSE_DETAILS|NO_DATA|NEED_CLARIFICATION|FOLLOW_UP|AVAILABILITY_CHECK",
  "answer_md": "string (Guidance text ONLY. No course lists.)",
  "selected_courses": [
    {
      "course_id": "string",
      "title": "string",
      "level": "string",
      "category": "string",
      "instructor": "string",
      "duration_hours": number|null,
      "reason": "string"
    }
  ],
  "skills_ordered": ["string"],
  "skills_with_courses": [
    {
      "skill_en": "string",
      "skill_ar": "string|null",
      "courses": ["course_id"]
    }
  ]
}
"""

# ============================================================
# 2) DYNAMIC DEVELOPER PROMPT
# ============================================================
DEVELOPER_PROMPT_TEMPLATE = """USER_QUERY: {USER_QUERY}
REQUEST_MODE: {MODE}
RENDER_MODE: {RENDER_MODE}
USER_LANGUAGE: {LANG}

SESSION_MEMORY:
{SESSION_MEMORY_JSON}

SKILLS_TO_COURSES_RESOLUTION (if available):
{RESOLUTION_JSON}

CATALOG_CONTEXT (only courses you are allowed to mention):
{CATALOG_CONTEXT_JSON}

Return JSON only using the required schema.
"""

ALLOWED_MODES = {
    "CAREER_GUIDANCE", "COURSE_SEARCH", "COURSE_DETAILS", 
    "NO_DATA", "NEED_CLARIFICATION", "SKILL_ROADMAP", "FOLLOW_UP", "AVAILABILITY_CHECK"
}

def generate_response(
    user_question: str,
    in_scope: bool,
    intent: str,
    target_categories: list,
    catalog_results: list = None,
    suggested_titles: list = None,
    user_language: str = "ar",
    chat_history: list = None,
    session_memory: dict = None,
    user_wants_courses: bool = False,
    extracted_skills: list = None,
    skill_course_map: dict = None,
    ordered_skills: list = None
) -> dict:
    """
    Generate final user-facing response using Groq LLM with Unified Grounding.
    """
    client = Groq(api_key=settings.groq_api_key)

    catalog_results = catalog_results or []
    chat_history = chat_history or []
    session_memory = session_memory or {}
    skill_course_map = skill_course_map or {}
    
    # [LOGIC] Determine Render Mode
    unique_course_count = len({c.course_id for c in catalog_results})
    render_mode = "single_course_expand" if unique_course_count == 1 else "multi_course_grouped"
    
    # 1) Build RESOLUTION_JSON
    # Transform skill_course_map to the expected structured format
    resolution_list = []
    if skill_course_map:
        for skill, courses in skill_course_map.items():
            c_ids = [str(c.course_id) if hasattr(c, 'course_id') else str(c.get('course_id')) for c in courses]
            resolution_list.append({
                "skill": skill,
                "courses": c_ids
            })
    resolution_json = json.dumps(resolution_list, ensure_ascii=False, indent=2)

    # 2) Build CATALOG_CONTEXT_JSON
    catalog_items = build_catalog_context(catalog_results)
    catalog_context_json = json.dumps(catalog_items, ensure_ascii=False, indent=2)

    # 3) Build SESSION_MEMORY_JSON
    # Filter critical keys only to reduce noise
    mem_keys = ["locked_role", "locked_skill", "locked_topic", "last_intent", "stage", "last_skill_query", "offset", "typo_correction"]
    filtered_mem = {k: session_memory.get(k) for k in mem_keys if k in session_memory}
    session_memory_json = json.dumps(filtered_mem, ensure_ascii=False, indent=2)
    
    # Render Prompt
    developer_prompt = DEVELOPER_PROMPT_TEMPLATE.format(
        USER_QUERY=user_question,
        MODE=intent, # Using intent as primary mode signal, LLM can refine
        RENDER_MODE=render_mode, # [NEW] Injected logic
        LANG=user_language,
        SESSION_MEMORY_JSON=session_memory_json,
        RESOLUTION_JSON=resolution_json,
        CATALOG_CONTEXT_JSON=catalog_context_json
    )

    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        # Inject history? The user prompt template didn't explicitly show history block, 
        # but standard practice is to include it. The "SESSION_MEMORY" covers state, but maybe recent messages help.
        # User template: "USER_QUERY: {USER_QUERY}" implies immediate turn. 
        # But we can prepend history messages to the messages_payload.
    ]
    
    # Add history messages
    for msg in chat_history:
        messages_payload.append({"role": msg["role"], "content": msg["content"]})
        
    # Append the final developer prompt as the latest user message
    messages_payload.append({"role": "user", "content": developer_prompt})

    # Call LLM
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages_payload,
            temperature=0.3, 
            max_tokens=1500, # Increased for detailed plans
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        
        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)
        
        # Validation / Safety Defaults
        mode = parsed.get("mode", "CAREER_GUIDANCE")
        if mode not in ALLOWED_MODES:
             mode = "CAREER_GUIDANCE"
        parsed["mode"] = mode
        
        if "selected_courses" not in parsed:
            parsed["selected_courses"] = []
            
        return parsed
        
    except Exception as e:
        logger.error(f"Generator failed: {e}")
        return {
            "mode": "CAREER_GUIDANCE",
            "answer_md": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
            "selected_courses": []
        }
