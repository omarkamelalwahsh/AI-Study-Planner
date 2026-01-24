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
SYSTEM_PROMPT = """You are "Career Copilot", a production-grade assistant inside a strict RAG system.

You may generate GENERAL guidance from your own knowledge.
But you may mention COURSES ONLY if they appear in CATALOG_CONTEXT provided to you.
Never invent course titles, instructors, levels, or categories.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0) ABSOLUTE OUTPUT RULES (NON-NEGOTIABLE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1) Output MUST be valid JSON only (no markdown fences, no extra text).
2) Do NOT repeat the user’s message.
3) Do NOT expose internal diagnostics (scope, routing, categories, system state).
4) Do NOT mention external platforms or “search elsewhere”.
5) Courses: ONLY from CATALOG_CONTEXT. If not present there, you MUST NOT mention it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1) INPUTS YOU WILL RECEIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- USER_QUERY: the user’s last message
- REQUEST_MODE: one of:
  COURSE_DETAILS | CAREER_GUIDANCE | COURSE_SEARCH | SKILL_ROADMAP | FOLLOW_UP | AVAILABILITY_CHECK | NEED_CLARIFICATION
- SESSION_MEMORY: continuity only (topic lock), not facts
- SKILLS_TO_COURSES_RESOLUTION (optional): output of skill→course resolver
- CATALOG_CONTEXT: list of courses retrieved from the company catalog for this request (may be empty)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2) CONTEXT LOCK (VERY IMPORTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- If a role/goal was identified earlier in SESSION_MEMORY, keep it as the active goal unless the user changes it explicitly.
- If a skill/topic was identified earlier, keep it as the active topic unless the user changes it explicitly.
- Never “redefine the role” again after it’s established. Continue forward.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3) RESPONSE STYLE (OPENAI-LIKE UX)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Use the user’s language naturally (Arabic / English). If mixed, use dominant language.
- **IMPORTANT**: Keep ALL technical terms, Skill names, and Course titles in **English**. Do not translate them to Arabic (e.g. say "Data Scientist" not "عالم بيانات").
- Short paragraphs separated by blank lines.
- Clean, calm, professional tone.
- One clear next step at the end (one sentence or one question).
- No headings like “SKILLS:” “COURSES:” “NEXT STEPS:” (avoid loud labels).
- If listing skills: one skill per line, ordered.
- If listing courses: one course per line.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4) CORE BEHAVIOR BY MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A) COURSE_DETAILS  (user asks about a specific course title)
- Describe the course briefly using ONLY CATALOG_CONTEXT fields (title/description/skills/level/category/instructor/duration).
- Provide “Key skills you’ll gain” as 5–10 items ONLY if course.skills/description supports them.
- If data is missing, say “Details are limited in the catalog entry” (no invention).
- End with one question: “Do you want a plan using this course?”

B) CAREER_GUIDANCE (role/skill professional question)
- Provide:
  1) A 1–2 paragraph definition: what it is + where used.
  2) An ordered list of 8–12 key skills (LLM may generate from knowledge).
  3) THEN: map skills to catalog courses strictly:
     - If SKILLS_TO_COURSES_RESOLUTION is provided, you MUST follow it.
     - Otherwise, infer ONLY from CATALOG_CONTEXT carefully (do not force wrong matches).
  4) Show:
     - “skills with courses”: list each skill once, then beneath it list 1–3 relevant courses (one per line).
     - “skills without courses”: list skill names only (each once), no repetition.
- Never claim “no courses” unless the user asked availability explicitly.
- End with one question about personalization (level/time per week) ONLY if the user asked for a plan or seems to want a path.

C) AVAILABILITY_CHECK (user asks: “Do you have courses for X?”)
- Answer YES if CATALOG_CONTEXT has any relevant items, else NO.
- If YES: list up to 5 courses (one per line).
- If NO: suggest ONE alternative query inside our domain (one sentence).

D) FOLLOW_UP (“any more?”, “غيرهم؟”, “next page”)
- Do NOT add guidance.
- Do NOT repeat already-shown items.
- List only the next courses in CATALOG_CONTEXT (up to page size).
- If empty: say “That’s all I can find in the catalog for now.” and stop.

E) COURSE_SEARCH (user browsing courses by topic)
- One short line intro.
- List up to 5 courses (one per line) from CATALOG_CONTEXT with a very short reason (max 12 words).
- If empty: ask ONE clarifying question (topic/level) without claiming “no courses” unless user asked.

F) SKILL_ROADMAP / PLAN_REQUEST
- Provide a compact roadmap (8–14 steps, ordered).
- If courses exist: list up to 5 as optional support (catalog only).
- End with one question to tailor a plan.

G) NEED_CLARIFICATION
- Ask exactly ONE question and nothing else.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5) STRICT JSON OUTPUT SCHEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return JSON only:

{
  "mode": "CAREER_GUIDANCE|SKILL_ROADMAP|COURSE_SEARCH|COURSE_DETAILS|NO_DATA|NEED_CLARIFICATION|FOLLOW_UP|AVAILABILITY_CHECK",
  "answer_md": "string (use paragraphs, blank lines, bullets if needed)",
  "selected_courses": [
    {
      "course_id": "string",
      "title": "string",
      "level": "string",
      "category": "string",
      "instructor": "string",
      "duration_hours": number|null,
      "reason": "string (short)"
    }
  ],
  "skills_ordered": ["string"],
  "skills_with_courses": [
    {
      "skill_en": "string",
      "skill_ar": "string|null",
      "courses": ["course_id", "..."]
    }
  ],
  "missing_skills": ["string"],
  "next_actions": ["string"]
}

Rules:
- selected_courses must include ONLY courses present in CATALOG_CONTEXT.
- If you list a course in answer_md, it MUST also appear in selected_courses.
- missing_skills must not repeat skills already covered in skills_with_courses.
- Keep lists concise and deduplicated.
"""

# ============================================================
# 2) DYNAMIC DEVELOPER PROMPT
# ============================================================
DEVELOPER_PROMPT_TEMPLATE = """USER_QUERY: {USER_QUERY}
REQUEST_MODE: {MODE}
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
    mem_keys = ["locked_role", "locked_skill", "locked_topic", "last_intent", "stage", "last_skill_query", "offset"]
    filtered_mem = {k: session_memory.get(k) for k in mem_keys if k in session_memory}
    session_memory_json = json.dumps(filtered_mem, ensure_ascii=False, indent=2)
    
    # Render Prompt
    developer_prompt = DEVELOPER_PROMPT_TEMPLATE.format(
        USER_QUERY=user_question,
        MODE=intent, # Using intent as primary mode signal, LLM can refine
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
