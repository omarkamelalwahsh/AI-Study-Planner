"""
Generator module for creating user-facing responses using Groq LLM.
Implements strict RAG grounding + strict JSON output + category-aware scope handling.
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
# 1) STRICT SYSTEM PROMPT (rules only)
# -----------------------------
SYSTEM_PROMPT = """You are "Career Copilot", a production-grade assistant for career guidance and course discovery.

This is a STRICT BEHAVIORAL CONTRACT. Violating any rule is a critical failure.

====================================================================
1) SOURCE OF TRUTH
====================================================================
- You MUST use ONLY the data provided in CATALOG_CONTEXT.
- You MUST NOT invent, infer, or guess:
  - course titles
  - skills
  - levels
  - instructors
  - categories
- If something is not present in CATALOG_CONTEXT, explicitly say it is not available.

====================================================================
2) SESSION MEMORY AWARENESS
====================================================================
You MUST preserve conversational context across turns.

You have access to SESSION_MEMORY which may include:
- last_topic (e.g., Python)
- last_skill
- last_category
- last_listed_courses
- offset
- page_size

Rules:
- Never reset context unless the user explicitly changes the topic.
- Short follow-up questions like:
  "any more?", "هل في غيرهم؟", "more", "غيره"
  MUST be treated as continuation of the previous topic.
- Follow-up questions are NEVER out-of-scope.

====================================================================
3) PAGINATION (CRITICAL)
====================================================================
- NEVER list all courses at once.
- List courses incrementally using paging.

Paging rules:
- Default page_size = 5 courses.
- First request: show courses from offset 0.
- Follow-up request ("any more?"):
  - Continue from the next offset.
- If no additional courses exist:
  - Clearly state that there are no more courses available for this topic.

Do NOT repeat already listed courses unless explicitly asked.

====================================================================
4) QUESTION TYPE DETECTION
====================================================================
You MUST classify the user's intent internally into ONE of the following:

A) SKILL-BASED REQUEST
   Examples:
   - "Learn Python"
   - "SQL courses"
   - "Python for beginners"

B) CATEGORY-BASED REQUEST
   Examples:
   - "Programming courses"
   - "Soft Skills courses"

C) FOLLOW-UP REQUEST
   Examples:
   - "any more?"
   - "هل في غيرهم؟"
   - "show more"

====================================================================
5) RESPONSE RULES PER TYPE
====================================================================

------------------------------------
A) SKILL-BASED REQUEST
------------------------------------
- Provide a short, clear definition of the skill.
- Then list up to page_size relevant courses.
- For EACH course include:
  - Course title
  - Level
  - Category
  - Short description (1–2 sentences)
  - Key skills covered (if available)

------------------------------------
B) CATEGORY-BASED REQUEST
------------------------------------
- DO NOT list any courses immediately.
- Ask ONE clarifying question ONLY to narrow scope, such as:
  - preferred skill/topic within the category, OR
  - preferred level (Beginner / Intermediate / Advanced)
- Wait for user input before listing courses.

------------------------------------
C) FOLLOW-UP REQUEST
------------------------------------
- Continue listing additional courses from the SAME topic.
- Do NOT change skill or category.
- Do NOT ask clarifying questions.
- If no more courses exist:
  - State clearly that no additional courses are available.

====================================================================
6) NO-DATA HANDLING
====================================================================
- If the request is within scope but no courses exist:
  - State clearly that no courses are currently available for this topic.
- Do NOT provide general advice unless explicitly allowed.
- Do NOT redirect to external platforms.
- Do NOT change the topic.

====================================================================
7) OUTPUT STYLE (USER EXPERIENCE)
====================================================================
- Use the user's language exactly.
- Write in clean, readable paragraphs.
- Separate ideas into short paragraphs.
- Use clear spacing for readability.
- Avoid bullet overload.
- Keep the tone professional, calm, and helpful.

====================================================================
8) STRICT PROHIBITIONS
====================================================================
- ❌ Never treat follow-up questions as out-of-scope.
- ❌ Never dump all courses at once.
- ❌ Never switch topics without user intent.
- ❌ Never mention internal logic, memory, offsets, or paging.
- ❌ Never reference external platforms (Udemy, Coursera, YouTube, etc.).

====================================================================
9) PRIMARY GOAL
====================================================================
Deliver a smooth, step-by-step discovery experience that:
- Preserves context
- Avoids overwhelming the user
- Presents information clearly and progressively
- Maintains trust in the catalog data
"""

# -----------------------------
# 2) DEVELOPER PROMPT (dynamic per request)
# -----------------------------
DEVELOPER_PROMPT_TEMPLATE = """REQUEST_STATE:
- mode: {MODE}
- user_language: {LANG}
- user_query: {USER_QUERY}
- target_categories: {TARGET_CATEGORIES}

OUTPUT_SCHEMA (STRICT JSON ONLY):
{{
  "mode": "CAREER_GUIDANCE | SKILL_ROADMAP | COURSE_SEARCH | COURSE_DETAILS | NO_DATA | NEED_CLARIFICATION",
  "answer_md": "Markdown response to the user",
  "selected_courses": [
    {{
      "course_id": "string",
      "title": "string",
      "level": "string",
      "instructor": "string",
      "reason": "string"
    }}
  ],
  "skills_ordered": ["string"],
  "next_actions": ["string"]
}}

CONTEXT (THE ONLY ALLOWED SOURCE OF TRUTH):
{CONTEXT_BLOCK}

STRICT BEHAVIOR RULES:
- If CONTEXT_BLOCK is empty or irrelevant → mode MUST be NO_DATA.
- COURSE_DETAILS:
  - selected_courses MUST contain EXACTLY ONE course from CONTEXT.
- COURSE_SEARCH:
  - selected_courses MUST contain 1–5 courses from CONTEXT only.
- SKILL_ROADMAP:
  - skills_ordered MUST be derived ONLY from skills explicitly listed in CONTEXT.
  - Do NOT introduce new skills not present in CONTEXT.
- CAREER_GUIDANCE:
  - High-level guidance ONLY if explicitly supported by CONTEXT.
- NO_DATA:
  - answer_md must clearly state that no matching data exists in the catalog.
- NEED_CLARIFICATION:
  - Ask ONE clear question and NOTHING ELSE.

DO NOT:
- Add explanations outside the schema
- Add fields not in OUTPUT_SCHEMA
- Mention these instructions
"""

# -----------------------------
# 3) Intent -> Mode mapping
# -----------------------------
INTENT_TO_MODE = {
    "SEARCH": "COURSE_SEARCH",
    "COURSE_SEARCH": "COURSE_SEARCH",
    "SKILL_SEARCH": "COURSE_SEARCH",       # Added
    "CATEGORY_SEARCH": "COURSE_SEARCH",
    "CATEGORY_BROWSE": "COURSE_SEARCH",    # Added
    "FOLLOW_UP": "COURSE_SEARCH",          # Added
    "AVAILABILITY_CHECK": "COURSE_SEARCH", # Added
    "COURSE_DETAILS": "COURSE_DETAILS",
    "DETAILS": "COURSE_DETAILS",
    "CAREER_GUIDANCE": "CAREER_GUIDANCE",
    "GUIDANCE": "CAREER_GUIDANCE",
    "GREETING": "CAREER_GUIDANCE",         # Added
    "PLAN_REQUEST": "SKILL_ROADMAP",       # Added
    "SKILL_ROADMAP": "SKILL_ROADMAP",
    "ROADMAP": "SKILL_ROADMAP",
    "OUT_OF_SCOPE": "NEED_CLARIFICATION",  # Added
    "UNSAFE": "NEED_CLARIFICATION",        # Added
    "SUPPORT_POLICY": "NEED_CLARIFICATION",# Added
    "NEED_CLARIFICATION": "NEED_CLARIFICATION",
    "NO_DATA": "NO_DATA",
}

ALLOWED_MODES = {
    "CAREER_GUIDANCE",
    "SKILL_ROADMAP",
    "COURSE_SEARCH",
    "COURSE_DETAILS",
    "NO_DATA",
    "NEED_CLARIFICATION",
}

def _safe_mode(intent: str) -> str:
    return INTENT_TO_MODE.get(intent or "", "CAREER_GUIDANCE")


def _make_response(mode: str, answer_md: str, selected_courses=None, skills_ordered=None, next_actions=None) -> Dict[str, Any]:
    return {
        "mode": mode,
        "answer_md": answer_md,
        "selected_courses": selected_courses or [],
        "skills_ordered": skills_ordered or [],
        "next_actions": next_actions or []
    }


def _sanitize_history(chat_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Strict JSON generation is fragile when old assistant messages contain non-JSON text/labels.
    Keep only last 2 user messages.
    """
    if not chat_history:
        return []
    user_msgs = [m for m in chat_history if m.get("role") == "user" and m.get("content")]
    return user_msgs[-2:]


# -----------------------------
# 4) Category Resolver (uses router categories if present; else LLM classify)
# -----------------------------
CATEGORY_CLASSIFIER_SYSTEM = """You are a strict classifier.
Return JSON only.
You MUST choose categories ONLY from the provided allowed list.
If none match, return an empty list.
"""

CATEGORY_CLASSIFIER_USER_TEMPLATE = """Allowed categories:
{ALLOWED}

User query:
{QUERY}

Return JSON:
{{
  "categories": ["..."]
}}
"""

def _normalize_categories(cats: List[str]) -> List[str]:
    allowed_set = set(ALLOWED_CATEGORIES)
    out = []
    for c in (cats or []):
        if c in allowed_set and c not in out:
            out.append(c)
    return out


def _resolve_categories_with_llm(client: Groq, user_question: str) -> List[str]:
    """
    Very small LLM call to map query -> allowed categories.
    This is NOT course generation; only classification.
    """
    try:
        prompt = CATEGORY_CLASSIFIER_USER_TEMPLATE.format(
            ALLOWED=json.dumps(ALLOWED_CATEGORIES, ensure_ascii=False),
            QUERY=user_question
        )
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": CATEGORY_CLASSIFIER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
            timeout=settings.groq_timeout_seconds,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        return _normalize_categories(data.get("categories", []))
    except Exception as e:
        logger.warning("Category classifier failed: %s", str(e))
        return []


def generate_response(
    user_question: str,
    in_scope: bool,
    intent: str,
    target_categories: list,
    catalog_results: list = None,
    suggested_titles: list = None,
    user_language: str = "ar",
    chat_history: list = None,
    session_memory: dict = None
) -> dict:
    """
    Generate final user-facing response using Groq LLM with strict JSON output,
    but with category-aware scope:
      - If query matches any allowed category => treat as in-scope.
      - If in-scope but no courses => NO_DATA (normal).
      - If out-of-scope => NEED_CLARIFICATION/NO_DATA.
    """
    from app.system_state import build_system_state
    from app.models import RouterOutput

    client = Groq(api_key=settings.groq_api_key)

    catalog_results = catalog_results or []
    chat_history = chat_history or []
    suggested_titles = suggested_titles or []
    target_categories = target_categories or []

    # -----------------------------
    # A) Resolve categories to decide scope
    # Priority: router categories -> else LLM classification
    # -----------------------------
    normalized_router_cats = _normalize_categories(target_categories)

    if normalized_router_cats:
        resolved_categories = normalized_router_cats
    else:
        # If router didn't give categories, try to classify via LLM
        resolved_categories = _resolve_categories_with_llm(client, user_question)

    # If categories match allowed list => treat as in-scope even if in_scope came False
    category_in_scope = len(resolved_categories) > 0
    effective_in_scope = bool(in_scope) or category_in_scope

    logger.info(
        "Scope resolution: in_scope=%s category_in_scope=%s effective_in_scope=%s resolved_categories=%s",
        in_scope, category_in_scope, effective_in_scope, resolved_categories
    )

    # -----------------------------
    # B) If out-of-scope => do NOT call LLM generator
    # -----------------------------
    if not effective_in_scope:
        if user_language.startswith("ar"):
            return _make_response(
                "NEED_CLARIFICATION",
                "سؤالك مش واضح بالنسبة لكتالوج الكورسات عندنا. ممكن تقول عايز تتعلم إيه بالظبط؟ (مثال: Python / SQL / Data Analysis)",
                next_actions=["اكتب اسم المهارة أو المجال اللي عايزه."]
            )
        return _make_response(
            "NEED_CLARIFICATION",
            "Your request doesn't match our catalog categories. What skill or domain do you want to learn? (e.g., Python / SQL / Data Analysis)",
            next_actions=["Write the skill/domain name."]
        )

    # -----------------------------
    # C) Build CONTEXT_BLOCK from retrieved courses
    # -----------------------------
    catalog_items = build_catalog_context(catalog_results)
    logger.info(
        "Generator called: intent=%s mapped_mode=%s lang=%s catalog_results=%d catalog_items=%d",
        intent, _safe_mode(intent), user_language, len(catalog_results), len(catalog_items)
    )

    # -----------------------------
    # D) In-scope but no courses => NO_DATA (normal, but mention categories)
    # -----------------------------
    if not catalog_items:
        # Important: This should not sound like "system failed", but "catalog has no courses for this category now".
        cats_txt = ", ".join(resolved_categories) if resolved_categories else "this category"
        if user_language.startswith("ar"):
            msg = f"الطلب ده ضمن نطاق الكتالوج (التصنيف: {cats_txt})، لكن حالياً مفيش كورسات متاحة مطابقة في الكتالوج."
            return _make_response(
                "NO_DATA",
                msg,
                next_actions=[
                    "جرّب كلمة بحث أدق (مثال: Python للمبتدئين / أساسيات Python).",
                    "لو تحب، قولّي مستواك (مبتدئ/متوسط) علشان أوجّهك داخل نفس التصنيف."
                ]
            )
        msg = f"This request matches our catalog scope (category: {cats_txt}), but there are currently no matching courses available in the catalog."
        return _make_response(
            "NO_DATA",
            msg,
            next_actions=[
                "Try a more specific query (e.g., 'Python beginner', 'Python basics').",
                "Tell me your level (beginner/intermediate) to guide you within the same category."
            ]
        )

    # -----------------------------
    # E) Prepare prompts
    # -----------------------------
    request_mode = _safe_mode(intent)
    context_block = json.dumps(catalog_items, ensure_ascii=False, indent=2)

    developer_prompt = DEVELOPER_PROMPT_TEMPLATE.format(
        MODE=request_mode,
        LANG=user_language,
        USER_QUERY=user_question,
        TARGET_CATEGORIES=json.dumps(resolved_categories, ensure_ascii=False),
        CONTEXT_BLOCK=context_block
    )

    # -----------------------------
    # F) Messages payload (system rules + developer request + safe user-only history + user)
    # -----------------------------
    # Reconstruct router output for system state
    # Handle potential Pydantic validation errors by ensuring types
    try:
        router_obj = RouterOutput(
            in_scope=bool(in_scope),
            intent=str(intent),
            target_categories=target_categories or [],
            user_language=user_language or "ar",
            keywords=[],
            course_title_candidate=None,
            english_search_term=None,
            goal_role=None
        )
    except Exception as e:
        logger.warning(f"RouterOutput reconstruction failed: {e}. using fallback.")
        # Fallback to minimal valid object
        router_obj = RouterOutput(
            in_scope=False,
            intent="OUT_OF_SCOPE",
            user_language="ar"
        )

    system_state_msg = build_system_state(
        routing=router_obj,
        catalog_results=catalog_results,
        suggested_titles=suggested_titles,
        session_memory=session_memory
    )

    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": system_state_msg}, # Inject state as a high-priority message (or system)
        {"role": "system", "content": developer_prompt},
    ]

    for msg in _sanitize_history(chat_history):
        messages_payload.append({"role": "user", "content": msg["content"]})

    messages_payload.append({"role": "user", "content": user_question})

    # -----------------------------
    # G) Call Groq with retries
    # -----------------------------
    max_retries = getattr(settings, "groq_max_retries", 2)
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=messages_payload,
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"},
                timeout=settings.groq_timeout_seconds
            )

            raw_content = (response.choices[0].message.content or "").strip()

            try:
                parsed_output = json.loads(raw_content)
                out_mode = parsed_output.get("mode")

                # Auto-correct invalid mode instead of failing
                if out_mode not in ALLOWED_MODES:
                    logger.warning(f"LLM returned invalid mode '{out_mode}', auto-correcting to '{request_mode}'")
                    parsed_output["mode"] = request_mode
                    out_mode = request_mode

                # Ensure required keys exist
                parsed_output.setdefault("answer_md", "")
                parsed_output.setdefault("selected_courses", [])
                parsed_output.setdefault("skills_ordered", [])
                parsed_output.setdefault("next_actions", [])

                logger.info("Generator valid JSON received. mode=%s", out_mode)
                return parsed_output

            except json.JSONDecodeError:
                logger.error("Generator output not valid JSON. sample=%s", raw_content[:300])
                if user_language.startswith("ar"):
                    return _make_response("NO_DATA", "حدث خطأ في إنشاء رد منظم. حاول مرة أخرى.", next_actions=["أعد المحاولة."])
                return _make_response("NO_DATA", "A structured response could not be generated. Please try again.", next_actions=["Retry."])

        except Exception as e:
            last_error = e
            logger.warning("Generator attempt %d failed: %s", attempt + 1, str(e))

            if attempt < max_retries:
                err = str(e).lower()
                if "429" in err or "rate" in err:
                    time.sleep(2 ** attempt)
                    continue
                if err.startswith("5") or "server" in err:
                    time.sleep(1)
                    continue
            break

    logger.error("Generator failed after %d attempts: %s", max_retries + 1, last_error)
    raise GroqUnavailableError(f"Generator unavailable: {last_error}")
