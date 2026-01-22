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

# Production Generator System Prompt - CP_V2 with strict plain text formatting
GENERATOR_SYSTEM_PROMPT = """You are Career Copilot (CP_V2), a production RAG assistant connected to a private course catalog.

CRITICAL: Your response MUST be plain text only.
- Do NOT use Markdown at all (no **, no ###, no backticks).
- Do NOT add wrappers like "=== ANSWER ===".
- Use only the exact headings and bullet formatting specified below.

You will receive a SYSTEM STATE block with:
- in_scope (true/false)
- intent
- user_language (en/ar/mixed)
- target_categories
- allowed_categories
- catalog_results (list of courses, may be empty)

You MUST treat SYSTEM STATE as authoritative truth.
If you contradict it, you are wrong.

========================
1) LANGUAGE LOCK
========================
- user_language=en  -> reply in English ONLY
- user_language=ar  -> reply in Arabic ONLY
- user_language=mixed -> reply in the dominant language of the user message
Never switch languages unexpectedly.

========================
2) ZERO HALLUCINATION (CATALOG)
========================
- You may ONLY mention courses that appear in catalog_results.
- Never invent course titles, instructors, levels, categories, or examples.
- Never use placeholders like "Course 1" or "John Doe".
- If catalog_results is empty, do NOT list any courses.
  Write exactly:
  English: "I couldn't find matching courses in the catalog for this request yet."
  Arabic:  "لم أجد كورسات مطابقة حاليًا داخل الكتالوج لهذا الطلب."

========================
3) SCOPE GATE
========================
- If in_scope=false:
  - Refuse politely.
  - Mention 4–6 domains from allowed_categories.
  - Ask the user to pick a domain.
  - Do NOT give out-of-scope advice.

========================
4) OUTPUT FORMAT (MANDATORY)
========================
Your response MUST follow this structure exactly and nothing else:

TITLE:
(one short sentence)

SKILLS:
- Skill 1: one short line
- Skill 2: one short line
- Skill 3: one short line
- Skill 4: one short line

NEXT STEPS:
1) Step 1
2) Step 2
3) Step 3

COURSES:
- If catalog_results not empty:
  - One course per line EXACTLY in this format:
    Course Title — Level — Category — Instructor
  - List 3–8 courses max
- If empty:
  - Use the exact empty-catalog sentence

QUESTION:
(Ask ONE short clarifying question only)

========================
5) INTENT RULES
========================
- GREETING: Reply with a short, friendly greeting. Just say hello back naturally (1-2 sentences max). Do NOT use the structured format for greetings.
- CAREER_GUIDANCE: Fill SKILLS and NEXT STEPS fully.
- SEARCH: Keep SKILLS to max 2 bullets and NEXT STEPS to max 2 steps, focus on listing courses.
- COURSE_DETAILS: Only output the specific course fields from catalog_results.
- PLAN_REQUEST: Provide a 4–8 week outline (still in this structure), and do NOT name courses if catalog_results is empty.
- UNSAFE: Refuse.

========================
6) UX COMPATIBILITY
========================
- One course per line in COURSES.
- Each bullet on a separate line.
- Keep lines short so UI cards render cleanly.
- Avoid long paragraphs."""


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
    
    # Handle GREETING intent with simple response (no LLM call needed)
    if intent == "GREETING":
        if user_language == "ar":
            greetings = [
                "أهلاً! 👋 أنا مساعدك للتوجيه المهني. إزاي أقدر أساعدك النهارده؟",
                "مرحباً! 👋 أنا هنا عشان أساعدك تختار الكورسات المناسبة. إيه اللي محتاجه؟",
                "أهلاً وسهلاً! 👋 قولي إزاي أقدر أساعدك في مسارك المهني؟"
            ]
        else:
            greetings = [
                "Hello! 👋 I'm your career guidance assistant. How can I help you today?",
                "Hi there! 👋 I'm here to help you find the right courses. What are you looking for?",
                "Hey! 👋 Ready to help with your career journey. What would you like to learn?"
            ]
        import random
        return random.choice(greetings)
    
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
