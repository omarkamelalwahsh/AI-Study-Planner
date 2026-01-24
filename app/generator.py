"""
Generator module for creating user-facing responses using Groq LLM.
Implements Unified Grounding: LLM has full access to catalog context but must strictly adhere to provided data.
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

# -----------------------------
# 1) UNIFIED SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = """You are “Career Copilot”, a senior professional career advisor.
You are part of a RAG-based system. You speak like a real human expert.

━━━━━━━━━━━━━━━━━━━━━━
CORE PRINCIPLES
━━━━━━━━━━━━━━━━━━━━━━
1) **STRICT RESPONSE STRUCTURE** (For Career Guidance/Skills):
   - **Step 1: Concept Definition**: Briefly explain the role or skill in Arabic (1-2 sentences).
   - **Step 2: Required Skills (ENGLISH ONLY)**: List the top 5-7 key technical/soft skills in English as bullet points.
   - **Step 3: Database Verification**: Check `CATALOG_CONTEXT`.
     - IF courses found matching these skills: "Great news! We have courses for these skills:" and list them.
     - IF NO courses found: "Currently, I don't see specific courses for this in our catalog, but these are the skills you should focus on."
   
2) **FULL ACCESS & TRUST**: 
   - You must base your course suggestions ONLY on `CATALOG_CONTEXT`.
   - Do NOT invent courses.

3) **FORMATTING**:
   - Use Markdown.
   - Speak in clear, professional Arabic (except for the Skills list which MUST be English).

━━━━━━━━━━━━━━━━━━━━━━
RESPONSE RULES
━━━━━━━━━━━━━━━━━━━━━━
A) "I want to be X" / "Guidance":
   - Follow the **STRICT RESPONSE STRUCTURE** above.
   
B) "Do you have courses?" / "List courses":
   - Use the `selected_courses` JSON field to populate the UI cards.
   - In text, give a brief intro.

C) "What skills?":
   - Follow Step 2 of the structure (English list).
"""

# -----------------------------
# 2) DYNAMIC DEVELOPER PROMPT
# -----------------------------
DEVELOPER_PROMPT_TEMPLATE = """REQUEST CONTEXT:
- User Query: {USER_QUERY}
- User Language: {LANG}
- User Explicitly Wants Courses: {WANTS_COURSES}
- Target Categories: {TARGET_CATEGORIES}
- Extracted Skills (Focus on these): {EXTRACTED_SKILLS}

CATALOG_CONTEXT (Ground Truth):
{CONTEXT_BLOCK}

SESSION HISTORY (For context only):
{HISTORY_BLOCK}

OUTPUT SCHEMA (STRICT JSON):
{{
  "mode": "CAREER_GUIDANCE | COURSE_SEARCH | COURSE_DETAILS | NO_DATA | NEED_CLARIFICATION",
  "answer_md": "Markdown response text.",
  "selected_courses": [
    {{
      "course_id": "string (MUST match ID in context)",
      "reason": "1 line reason why this fits"
    }}
  ],
  "skills_ordered": ["skill1", "skill2", "..."]
}}

INSTRUCTIONS:
1. If 'User Explicitly Wants Courses' is TRUE:
   - You MUST pick best matches from CATALOG_CONTEXT and put them in `selected_courses`.
   - If CATALOG_CONTEXT is empty, set mode="NO_DATA" and explain nicely in `answer_md`.
   
2. If 'User Explicitly Wants Courses' is FALSE:
   - Focus on `answer_md` (Guidance/Explanation).
   - `selected_courses` should be EMPTY unless you feel strongly that showing a specific card is critical. Usually, just explain in text.
   - For CAREER_GUIDANCE intent: You MUST populate `skills_ordered` with 6-10 key skills (mix of technical and soft), even if CATALOG_CONTEXT is empty.
   
3. COURSE_DETAILS intent:
   - `selected_courses` must have exactly 1 item.

4. Language:
   - Reply in {LANG}.
"""

ALLOWED_MODES = {
    "CAREER_GUIDANCE", "COURSE_SEARCH", "COURSE_DETAILS", 
    "NO_DATA", "NEED_CLARIFICATION", "SKILL_ROADMAP"
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
    extracted_skills: str = None # [NEW]
) -> dict:
    """
    Generate final user-facing response using Groq LLM with Unified Grounding.
    """
    client = Groq(api_key=settings.groq_api_key)

    catalog_results = catalog_results or []
    chat_history = chat_history or []
    
    # Build context block
    catalog_items = build_catalog_context(catalog_results)
    
    # Prepare prompts
    context_block = json.dumps(catalog_items, ensure_ascii=False, indent=2)
    history_block = json.dumps([m for m in chat_history if m['role']=='user'][-2:], ensure_ascii=False)
    
    developer_prompt = DEVELOPER_PROMPT_TEMPLATE.format(
        USER_QUERY=user_question,
        LANG=user_language,
        WANTS_COURSES=str(user_wants_courses),
        TARGET_CATEGORIES=str(target_categories),
        EXTRACTED_SKILLS=extracted_skills or "None",
        CONTEXT_BLOCK=context_block,
        HISTORY_BLOCK=history_block
    )

    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": developer_prompt}
    ]

    # Call LLM
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages_payload,
            temperature=0.3, # Slightly creativity allowed for natural guidance
            max_tokens=1024,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds
        )
        
        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)
        
        # Validation / Safety
        mode = parsed.get("mode", "CAREER_GUIDANCE")
        if mode not in ALLOWED_MODES:
            mode = "CAREER_GUIDANCE"
        parsed["mode"] = mode
        
        return parsed
        
    except Exception as e:
        logger.error(f"Generator failed: {e}")
        # Fallback
        return {
            "mode": "CAREER_GUIDANCE",
            "answer_md": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى." if user_language=="ar" else "Sorry, a technical error occurred.",
            "selected_courses": []
        }
