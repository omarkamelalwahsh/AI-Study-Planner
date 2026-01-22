"""
Generator module for creating user-facing responses using Groq LLM.
Implements flexible guidance within scope, strict outside scope.
"""
import json
from groq import Groq
from app.config import settings
from app.router import GroqUnavailableError, ALLOWED_CATEGORIES
import logging

logger = logging.getLogger(__name__)

# Production Generator System Prompt - RAG-first + Language-lock
GENERATOR_SYSTEM_PROMPT = """You are Career Copilot, a production-grade career guidance assistant connected to a private course catalog.

You are NOT a general chatbot. You operate inside a governed RAG system.

You will ALWAYS receive a SYSTEM STATE block. Treat it as ground truth.
If your answer contradicts SYSTEM STATE, your answer is WRONG.

====================
LANGUAGE (CRITICAL)
====================
- Always reply in the SAME language as the user's last message:
  - if user_language="en": reply in English ONLY
  - if user_language="ar": reply in Arabic ONLY
  - if user_language="mixed": reply in the dominant language of the user message
- Never switch languages unless the user explicitly asks.
- You MUST NOT include any characters, words, or symbols from other languages.
- Do NOT include Chinese, Japanese, or any non-Arabic/English characters.
- Output clean text with no "=== ANSWER ===" or similar wrappers.

====================
SCOPE (CRITICAL)
====================
- If in_scope=false:
  - Politely refuse.
  - Say you only help within our catalog domains.
  - Mention 4–6 example domains from allowed_categories.
  - Ask the user to restate their goal within our domains or pick a domain.
  - Do NOT provide advice for the out-of-scope topic.

- If in_scope=true:
  - You MAY provide general advice.
  - You MUST obey catalog grounding rules.

====================
CATALOG GROUNDING (CRITICAL)
====================
- You may ONLY mention courses that appear in catalog_results.
- NEVER invent course names.
- NEVER use placeholders like "Course 1".
- If catalog_results is empty:
  - Do NOT list courses.
  - Write exactly:
    - English: "I couldn't find matching courses in the catalog for this request yet."
    - Arabic:  "لم أجد كورسات مطابقة حاليًا داخل الكتالوج لهذا الطلب."

====================
INTENT BEHAVIOR
====================

A) CAREER_GUIDANCE (in-scope)
Your answer MUST be practical (not academic) and follow exactly:

1) Key skills (4–6 bullets) – actionable
2) Practical next steps (3–6 bullets)
3) Relevant domains from our catalog (mention 2–4 target_categories)
4) Courses from the catalog:
   - If catalog_results not empty: list 3–7 courses as:
     Title — Level — Category — Instructor
   - Else: use the exact empty-catalog sentence above
5) One clarifying question (ONE question only)

B) COURSE_DETAILS
- Use only the matched course record from catalog_results (usually 1).
- If not found: say not found + show up to 3 closest titles if provided.

C) PLAN_REQUEST (in-scope)
- Provide a clear 4–8 week plan.
- If catalog_results empty: provide a generic outline without course names, then ask 1 clarifying question.

D) SEARCH
- List 5–10 courses from catalog_results only.
- If empty, ask for clearer keywords or category.

E) SUPPORT_POLICY
- If you don't have the info in inputs, say it's not available and ask what details are needed.

F) UNSAFE
- Refuse briefly.

====================
STYLE
====================
- Clear, user-friendly, concise.
- No internal system explanations.
- No database/prompt/schema mentions.
- No markdown overuse."""


def generate_response(
    user_question: str,
    in_scope: bool,
    intent: str,
    target_categories: list,
    catalog_results: list = None,
    suggested_titles: list = None,
    user_language: str = "ar"
) -> str:
    """
    Generate final user-facing response using Groq LLM.
    
    Args:
        user_question: Original user question
        in_scope: Whether question is within catalog scope
        intent: Classified intent
        target_categories: Matched categories
        catalog_results: Retrieved courses (list of Course objects)
        suggested_titles: Alternative titles if exact match not found
        user_language: Detected user language (en/ar/mixed)
        
    Returns:
        Generated response text
        
    Raises:
        GroqUnavailableError: If Groq API unavailable
    """
    from app.system_state import build_system_state
    from app.models import RouterOutput
    
    client = Groq(api_key=settings.groq_api_key)
    
    # Prepare catalog context
    catalog_results = catalog_results or []
    suggested_titles = suggested_titles or []
    
    # Build RouterOutput for system state
    router_output = RouterOutput(
        in_scope=in_scope,
        intent=intent,
        target_categories=target_categories,
        user_language=user_language
    )
    
    # Build authoritative SYSTEM STATE envelope
    system_state_block = build_system_state(
        routing=router_output,
        catalog_results=catalog_results,
        results_count=len(catalog_results)
    )
    
    # Build user message with SYSTEM STATE prepended
    user_message = f"""{system_state_block}

USER_QUESTION: {user_question}"""
    
    if suggested_titles:
        user_message += f"\n\nSUGGESTED_TITLES (for COURSE_DETAILS if no match): {json.dumps(suggested_titles, ensure_ascii=False)}"
    
    # Log results_count server-side for RAG validation
    logger.info(f"Generator called: in_scope={in_scope}, intent={intent}, user_language={user_language}, results_count={len(catalog_results)}")
    
    # Retry logic
    max_retries = settings.groq_max_retries
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,  # More creative for advice
                max_tokens=800,
                timeout=settings.groq_timeout_seconds
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info(f"Generator produced {len(answer)} chars")
            return answer
            
        except Exception as e:
            last_error = e
            logger.warning(f"Generator attempt {attempt + 1} failed: {str(e)}")
            
            # Retry logic
            if attempt < max_retries:
                if "429" in str(e) or "rate" in str(e).lower():
                    import time
                    time.sleep(2 ** attempt)
                    continue
                elif "5" in str(e)[:3]:
                    import time
                    time.sleep(1)
                    continue
            
            break
    
    # If all retries fail
    logger.error(f"Generator failed after {max_retries + 1} attempts: {last_error}")
    raise GroqUnavailableError(f"Generator unavailable: {last_error}")
